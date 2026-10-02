"""O agente de vendas em LangGraph (PRD 5, 7.4, 7.5 e 7.6).

guardrail → triage → tool → reply → verify → act, com arestas condicionais pelos limiares
de graph.yaml. Em modo `both` os dois providers rodam em paralelo, os dois vão para
`metrics` e só o primário segue no fluxo: é a tool escolhida por ele que roda.
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
from app.dataset import QuestionInput
from app.metrics.pricing import load_pricing
from app.providers.base import DecisionProvider, NodeSpec, ProviderResult
from app.providers.jev import JevProvider
from app.providers.llm import LLMProvider
from app.providers.replay import FIXTURES_DIR, ReplayProvider, llm_fixture_dir
from app.providers.reply import LLMReplyWriter, ReplayReplyWriter, ReplyResult, ReplyWriter
from app.specs import GUARDRAIL, TRIAGE, VERIFY
from app.tools import (
    NO_TOOL,
    TOOLS,
    PostgresToolRunner,
    ReplayToolRunner,
    ToolResult,
    ToolRunner,
)

__all__ = ["Event", "Providers", "ReplyResult", "RunResult", "build_providers", "run_question"]

Action = Literal["auto", "human", "blocked"]

GUARDRAIL_REASONS = {
    "injection": "tentativa de manipular o assistente",
    "dado_sensivel": "pede ou contém dado pessoal sensível",
    "fora_escopo": "fora do escopo de vendas",
}


class Event(BaseModel):
    type: Literal[
        "run.started",
        "node.started",
        "provider.finished",
        "tool.finished",
        "node.finished",
        "run.finished",
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
    question_id: str
    question: str
    guardrail: dict | None
    triage: dict | None
    tool_result: ToolResult | None
    draft_reply: str | None
    verify: dict | None
    action: Action
    reason: str | None  # por que não foi `auto`, em linguagem simples
    path: list[str]
    metrics: list[NodeMetric]
    errors: list[str]


class SalesState(TypedDict):
    run_id: str
    question: dict  # id e text; os rótulos do golden set nunca entram no estado
    guardrail: dict | None
    triage: dict | None
    tool_result: dict | None
    draft_reply: str | None
    verify: dict | None
    action: Action | None
    reason: str | None
    metrics: Annotated[list[NodeMetric], operator.add]
    path: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]


@dataclass
class Providers:
    jev: DecisionProvider
    llm: DecisionProvider
    reply: ReplyWriter
    tools: ToolRunner
    llm_by_node: dict[str, DecisionProvider] = field(default_factory=dict)

    def get(self, name: str, node: str) -> DecisionProvider:
        return self.jev if name == "jev" else self.llm_by_node.get(node, self.llm)


def build_providers(
    config: GraphConfig, simulate_latency: bool = True, fixtures_dir: Path = FIXTURES_DIR
) -> Providers:
    if config.mode == "replay":
        llm_dir = llm_fixture_dir(config.llm_prompt_style)
        return Providers(
            jev=ReplayProvider("jev", simulate_latency, fixtures_dir),
            llm=ReplayProvider("llm", simulate_latency, fixtures_dir, llm_dir),
            reply=ReplayReplyWriter(simulate_latency, fixtures_dir, llm_dir),
            tools=ReplayToolRunner(simulate_latency, fixtures_dir),
        )
    pricing = load_pricing()
    return Providers(
        jev=JevProvider(pricing),
        llm=LLMProvider(config.llm_model, pricing, prompt_style=config.llm_prompt_style),
        reply=LLMReplyWriter(config.llm_model, pricing),
        tools=PostgresToolRunner(),
        llm_by_node={
            node: LLMProvider(model, pricing, prompt_style=config.llm_prompt_style)
            for node, model in config.llm_model_overrides.items()
        },
    )


# Regras das arestas (PRD 7.6). Recebem as respostas do primário, já serializadas.


def blocked_by(guardrail: dict, config: GraphConfig) -> list[str]:
    limit = config.thresholds.guardrail_block
    return [q for q, answer in guardrail.items() if answer["value"] >= limit]


def triage_reason(triage: dict, config: GraphConfig) -> str | None:
    answer = triage["tool"]
    if answer["value"] == NO_TOOL:
        return "nenhuma consulta disponível responde a pergunta"
    confidence = answer.get("confidence") or 0
    if confidence < config.thresholds.triage_min_confidence:
        return (
            f"confiança na escolha da consulta abaixo do limiar "
            f"({confidence:.0%} < {config.thresholds.triage_min_confidence:.0%})"
        )
    return None


def verify_reason(verify: dict, config: GraphConfig) -> str | None:
    t = config.thresholds
    if verify["fiel_aos_dados"]["value"] < t.verify_min_faithful:
        return "a verificação não confirmou que a resposta é fiel aos dados"
    if verify["inventa_numero"]["value"] >= t.verify_max_invented:
        return "a verificação apontou número que não está nos dados"
    return None


def payload(state: SalesState, node: NodeSpec) -> dict:
    """O mesmo payload para os dois providers. `question_id` serve ao replay."""
    data = {"question_id": state["question"]["id"]}
    for name in node.state_fields:
        value = state[name]
        if name == "question":
            value = value["text"]
        elif name == "tool_result" and value is not None:
            value = {k: value[k] for k in ("tool", "columns", "rows")}
        data[name] = value
    return data


def build_graph(config: GraphConfig, providers: Providers, emit: Callable):
    def decision_node(spec: NodeSpec):
        async def run(state: SalesState) -> dict:
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
            if spec.name == "guardrail" and answers and (risks := blocked_by(answers, config)):
                reasons = ", ".join(GUARDRAIL_REASONS[r] for r in risks)
                update |= {"action": "blocked", "reason": reasons}
            await emit("node.finished", spec.name, {"primary": primary, "answers": answers})
            return update

        return run

    async def tool(state: SalesState) -> dict:
        await emit("node.started", "tool")
        name = state["triage"]["tool"]["value"]
        update = {"path": ["tool"]}
        try:
            result = await providers.tools.run(name)
        except Exception as error:
            update["errors"] = [f"tool/{name}: {type(error).__name__}: {error}"]
            await emit("tool.finished", "tool", {"tool": name, "error": str(error)})
        else:
            update["tool_result"] = result.model_dump(mode="json")
            await emit("tool.finished", "tool", update["tool_result"])
        await emit("node.finished", "tool", {"tool": name, "ok": "tool_result" in update})
        return update

    async def reply(state: SalesState) -> dict:
        await emit("node.started", "reply")
        update = {"path": ["reply"]}
        result = state["tool_result"]
        tool_spec = TOOLS[result["tool"]]
        data = {
            "question_id": state["question"]["id"],
            "question": state["question"]["text"],
            "tool": {"name": tool_spec.name, "title": tool_spec.title},
            "data": {"columns": result["columns"], "rows": result["rows"]},
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

    async def act(state: SalesState) -> dict:
        await emit("node.started", "act")
        reason = None
        if state["guardrail"] is None or state["triage"] is None:
            reason = "uma das decisões falhou"
        elif reason := triage_reason(state["triage"], config):
            pass
        elif state["tool_result"] is None:
            reason = "a consulta aos dados falhou"
        elif state["draft_reply"] is None:
            reason = "a resposta não foi gerada"
        elif state["verify"] is None:
            reason = "a verificação falhou"
        else:
            reason = verify_reason(state["verify"], config)
        action = "human" if reason else "auto"
        await emit("node.finished", "act", {"action": action, "reason": reason})
        return {"action": action, "reason": reason, "path": ["act"]}

    def after_guardrail(state: SalesState) -> str:
        if state["action"] == "blocked":
            return END
        return "triage" if state["guardrail"] is not None else "act"

    def after_triage(state: SalesState) -> str:
        triage = state["triage"]
        return "act" if triage is None or triage_reason(triage, config) else "tool"

    def after_tool(state: SalesState) -> str:
        return "reply" if state["tool_result"] is not None else "act"

    def after_reply(state: SalesState) -> str:
        return "verify" if state["draft_reply"] is not None else "act"

    return (
        StateGraph(SalesState)
        .add_node("guardrail", decision_node(GUARDRAIL))
        .add_node("triage", decision_node(TRIAGE))
        .add_node("tool", tool)
        .add_node("reply", reply)
        .add_node("verify", decision_node(VERIFY))
        .add_node("act", act)
        .add_edge(START, "guardrail")
        .add_conditional_edges("guardrail", after_guardrail, ["triage", "act", END])
        .add_conditional_edges("triage", after_triage, ["tool", "act"])
        .add_conditional_edges("tool", after_tool, ["reply", "act"])
        .add_conditional_edges("reply", after_reply, ["verify", "act"])
        .add_edge("verify", "act")
        .add_edge("act", END)
        .compile()
    )


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


async def run_question(
    question: QuestionInput,
    config: GraphConfig,
    emit: EventSink | None = None,
    providers: Providers | None = None,
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
        data={
            "question_id": question.id,
            "question": question.text,
            "mode": config.mode,
            "config_version": config.config_version,
        },
    )
    graph = build_graph(config, providers, send)
    state = await graph.ainvoke(
        {
            "run_id": run_id,
            "question": {"id": question.id, "text": question.text},
            "guardrail": None,
            "triage": None,
            "tool_result": None,
            "draft_reply": None,
            "verify": None,
            "action": None,
            "reason": None,
            "metrics": [],
            "path": [],
            "errors": [],
        }
    )
    result = RunResult(
        run_id=run_id,
        config_version=config.config_version,
        mode=config.mode,
        question_id=question.id,
        question=question.text,
        guardrail=state["guardrail"],
        triage=state["triage"],
        tool_result=state["tool_result"],
        draft_reply=state["draft_reply"],
        verify=state["verify"],
        action=state["action"],
        reason=state["reason"],
        path=state["path"],
        metrics=state["metrics"],
        errors=state["errors"],
    )
    await send("run.finished", data=result.model_dump(mode="json"))
    return result
