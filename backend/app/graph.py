"""O pipeline de triagem em LangGraph (PRD 5, 7.4, 7.5 e 7.6).

guardrail → triage → reply → verify → act, com arestas condicionais pelos limiares de
graph.yaml. Em modo `both` os dois providers rodam em paralelo, os dois vão para
`metrics` e só o primário segue no fluxo.
"""

import asyncio
import operator
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.config import GraphConfig
from app.dataset import TicketInput, load_policy
from app.metrics.pricing import load_pricing
from app.providers.base import DecisionProvider, NodeSpec, ProviderResult
from app.providers.jev import JevProvider
from app.providers.llm import LLMProvider
from app.providers.replay import FIXTURES_DIR, ReplayProvider
from app.providers.reply import LLMReplyWriter, ReplayReplyWriter, ReplyResult, ReplyWriter
from app.specs import GUARDRAIL, TRIAGE, VERIFY

__all__ = ["Event", "Providers", "ReplyResult", "RunResult", "build_providers", "run_ticket"]

Action = Literal["auto", "human", "blocked"]


class Event(BaseModel):
    type: Literal[
        "run.started", "node.started", "provider.finished", "node.finished", "run.finished"
    ]
    run_id: str
    node: str | None = None
    data: dict = {}


EventSink = Callable[[Event], Awaitable[None]]


class NodeMetric(ProviderResult):
    node: str
    is_primary: bool


class RunResult(BaseModel):
    run_id: str
    config_version: str
    mode: Literal["replay", "live"]
    ticket_id: str
    guardrail: dict | None
    triage: dict | None
    draft_reply: str | None
    verify: dict | None
    action: Action
    path: list[str]
    metrics: list[NodeMetric]
    errors: list[str]


class TriageState(TypedDict):
    run_id: str
    ticket: dict  # id, text, channel; os rótulos do golden set nunca entram no estado
    policy: str
    guardrail: dict | None
    triage: dict | None
    draft_reply: str | None
    verify: dict | None
    action: Action | None
    metrics: Annotated[list[NodeMetric], operator.add]
    path: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]


@dataclass
class Providers:
    jev: DecisionProvider
    llm: DecisionProvider
    reply: ReplyWriter
    llm_by_node: dict[str, DecisionProvider] = field(default_factory=dict)

    def get(self, name: str, node: str) -> DecisionProvider:
        return self.jev if name == "jev" else self.llm_by_node.get(node, self.llm)


def build_providers(
    config: GraphConfig, simulate_latency: bool = True, fixtures_dir: Path = FIXTURES_DIR
) -> Providers:
    if config.mode == "replay":
        return Providers(
            jev=ReplayProvider("jev", simulate_latency, fixtures_dir),
            llm=ReplayProvider("llm", simulate_latency, fixtures_dir),
            reply=ReplayReplyWriter(simulate_latency, fixtures_dir),
        )
    pricing = load_pricing()
    return Providers(
        jev=JevProvider(pricing),
        llm=LLMProvider(config.llm_model, pricing),
        reply=LLMReplyWriter(config.llm_model, pricing),
        llm_by_node={
            node: LLMProvider(model, pricing) for node, model in config.llm_model_overrides.items()
        },
    )


# Regras das arestas (PRD 7.6). Recebem as respostas do primário, já serializadas.


def is_blocked(guardrail: dict, config: GraphConfig) -> bool:
    limit = config.thresholds.guardrail_block
    return any(answer["value"] >= limit for answer in guardrail.values())


def triage_needs_human(triage: dict, config: GraphConfig) -> bool:
    return triage["fila"]["confidence"] < config.thresholds.triage_min_confidence


def verify_needs_human(verify: dict, config: GraphConfig) -> bool:
    t = config.thresholds
    return (
        verify["segue_politica"]["value"] < t.verify_min_policy
        or verify["promete_fora"]["value"] >= t.verify_max_overpromise
    )


def payload(state: TriageState, node: NodeSpec) -> dict:
    """O mesmo payload para os dois providers. `ticket_id` serve ao replay."""
    data = {"ticket_id": state["ticket"]["id"]}
    for name in node.state_fields:
        value = state[name]
        data[name] = {k: v for k, v in value.items() if k != "id"} if name == "ticket" else value
    return data


def build_graph(config: GraphConfig, providers: Providers, emit: Callable):
    def decision_node(spec: NodeSpec):
        async def run(state: TriageState) -> dict:
            await emit("node.started", spec.name)
            names = config.providers_for(spec.name)
            primary = config.primary_for(spec.name)
            data = payload(state, spec)

            async def call(name: str) -> NodeMetric | Exception:
                # Cada provider é emitido ao terminar: o Jev aparece antes do LLM na tela.
                is_primary = name == primary
                try:
                    outcome = await providers.get(name, spec.name).decide(spec, data)
                except Exception as error:
                    await emit(
                        "provider.finished",
                        spec.name,
                        {"provider": name, "is_primary": is_primary, "error": str(error)},
                    )
                    return error
                metric = NodeMetric(**outcome.model_dump(), node=spec.name, is_primary=is_primary)
                await emit("provider.finished", spec.name, metric.model_dump(mode="json"))
                return metric

            outcomes = await asyncio.gather(*(call(name) for name in names))

            metrics, errors, answers = [], [], None
            for name, outcome in zip(names, outcomes, strict=True):
                where = f"{spec.name}/{name}"
                if isinstance(outcome, Exception):
                    errors.append(f"{where}: {type(outcome).__name__}: {outcome}")
                    continue
                metrics.append(outcome)
                if not outcome.parse_ok:
                    errors.append(f"{where}: resposta fora do schema (parse_ok=False)")
                elif not outcome.values_in_schema:
                    errors.append(f"{where}: valor fora das opções (values_in_schema=False)")
                elif outcome.is_primary:
                    answers = {q: a.model_dump() for q, a in outcome.answers.items()}

            update = {spec.name: answers, "metrics": metrics, "path": [spec.name], "errors": errors}
            if spec.name == "guardrail" and answers and is_blocked(answers, config):
                update["action"] = "blocked"
            await emit("node.finished", spec.name, {"primary": primary, "answers": answers})
            return update

        return run

    async def reply(state: TriageState) -> dict:
        await emit("node.started", "reply")
        update = {"path": ["reply"]}
        data = {
            "ticket_id": state["ticket"]["id"],
            "ticket": payload(state, TRIAGE)["ticket"],
            "policy": state["policy"],
            "triage": state["triage"],
        }
        try:
            written = await providers.reply.write(data)
        except Exception as error:
            update["errors"] = [f"reply/llm: {type(error).__name__}: {error}"]
            await emit("provider.finished", "reply", {"provider": "llm", "error": str(error)})
        else:
            metric = NodeMetric(
                provider="llm",
                model=written.model,
                answers={},
                latency_ms=written.latency_ms,
                tokens_in=written.tokens_in,
                tokens_out=written.tokens_out,
                cost_usd=written.cost_usd,
                parse_ok=True,
                values_in_schema=True,
                raw={"text": written.text},
                node="reply",
                is_primary=True,
            )
            update |= {"draft_reply": written.text, "metrics": [metric]}
            await emit("provider.finished", "reply", metric.model_dump(mode="json"))
        await emit("node.finished", "reply", {"draft_reply": update.get("draft_reply")})
        return update

    async def act(state: TriageState) -> dict:
        await emit("node.started", "act")
        complete = all(
            state[k] is not None for k in ("guardrail", "triage", "draft_reply", "verify")
        )
        needs_human = (
            not complete
            or triage_needs_human(state["triage"], config)
            or verify_needs_human(state["verify"], config)
        )
        action = "human" if needs_human else "auto"
        await emit("node.finished", "act", {"action": action})
        return {"action": action, "path": ["act"]}

    def after_guardrail(state: TriageState) -> str:
        if state["action"] == "blocked":
            return END
        return "triage" if state["guardrail"] is not None else "act"

    def after_triage(state: TriageState) -> str:
        triage = state["triage"]
        return "act" if triage is None or triage_needs_human(triage, config) else "reply"

    def after_reply(state: TriageState) -> str:
        return "verify" if state["draft_reply"] is not None else "act"

    return (
        StateGraph(TriageState)
        .add_node("guardrail", decision_node(GUARDRAIL))
        .add_node("triage", decision_node(TRIAGE))
        .add_node("reply", reply)
        .add_node("verify", decision_node(VERIFY))
        .add_node("act", act)
        .add_edge(START, "guardrail")
        .add_conditional_edges("guardrail", after_guardrail, ["triage", "act", END])
        .add_conditional_edges("triage", after_triage, ["reply", "act"])
        .add_conditional_edges("reply", after_reply, ["verify", "act"])
        .add_edge("verify", "act")
        .add_edge("act", END)
        .compile()
    )


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


async def run_ticket(
    ticket: TicketInput,
    config: GraphConfig,
    emit: EventSink | None = None,
    providers: Providers | None = None,
    policy: str | None = None,
    simulate_latency: bool = True,
    run_id: str | None = None,
) -> RunResult:
    run_id = run_id or new_run_id()
    providers = providers or build_providers(config, simulate_latency)

    async def send(type: str, node: str | None = None, data: dict | None = None) -> None:
        if emit is not None:
            await emit(Event(type=type, run_id=run_id, node=node, data=data or {}))

    await send(
        "run.started",
        data={"ticket_id": ticket.id, "mode": config.mode, "config_version": config.config_version},
    )
    graph = build_graph(config, providers, send)
    state = await graph.ainvoke(
        {
            "run_id": run_id,
            "ticket": {"id": ticket.id, "text": ticket.text, "channel": ticket.channel},
            "policy": policy if policy is not None else load_policy(),
            "guardrail": None,
            "triage": None,
            "draft_reply": None,
            "verify": None,
            "action": None,
            "metrics": [],
            "path": [],
            "errors": [],
        }
    )
    result = RunResult(
        run_id=run_id,
        config_version=config.config_version,
        mode=config.mode,
        ticket_id=ticket.id,
        guardrail=state["guardrail"],
        triage=state["triage"],
        draft_reply=state["draft_reply"],
        verify=state["verify"],
        action=state["action"],
        path=state["path"],
        metrics=state["metrics"],
        errors=state["errors"],
    )
    await send("run.finished", data=result.model_dump(mode="json"))
    return result
