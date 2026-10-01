"""Métricas de um lote, por pergunta, por node e por provider (PRD 9.2).

Denominadores: um ticket só conta para um node se o provider foi chamado nele. Resposta que
não veio (falha de parsing) conta como erro. As perguntas de `verify` não têm rótulo no
golden set: entram em latência, custo e concordância, não em acurácia.
"""

import math
from typing import Literal

from pydantic import BaseModel

from app.config import GraphConfig
from app.dataset import Ticket
from app.graph import NodeMetric, RunResult
from app.specs import NODE_SPECS

PROVIDERS = ("jev", "llm")


class QuestionSummary(BaseModel):
    n: int
    accuracy: float | None
    f1_macro: float | None = None  # só fila
    mae: float | None = None  # só urgência


class NodeSummary(BaseModel):
    calls: int
    latency_p50: float | None
    latency_p95: float | None
    tokens_in: int
    tokens_out: int
    cost_total: float
    parse_fail_rate: float
    out_of_schema_rate: float
    latencies: list[float]  # amostras, para o histograma do dashboard


class ProviderSummary(BaseModel):
    """Só os nodes de decisão: o `reply` é do LLM em qualquer configuração."""

    model: str
    accuracy: float | None
    cost_total: float
    cost_per_1000: float
    latency_p95: float | None


class TicketRow(BaseModel):
    ticket_id: str
    tags: list[str]
    action: str | None
    answers: dict[str, dict[str, str | int | float | None]]  # pergunta -> provider -> valor
    labels: dict[str, str | int | bool]
    disagrees: bool
    wrong: bool  # o primário errou alguma pergunta com rótulo
    has_error: bool  # a execução registrou erro


class BatchReport(BaseModel):
    batch_id: str
    config_version: str
    mode: Literal["replay", "live"]
    llm_model: str
    primary: str
    n: int
    errors: int
    by_provider: dict[str, ProviderSummary]
    by_node: dict[str, dict[str, NodeSummary]]
    by_question: dict[str, dict[str, QuestionSummary]]
    agreement: dict[str, float]
    tickets: list[TicketRow]


QUESTIONS = {q.name: (node, q.type) for node, spec in NODE_SPECS.items() for q in spec.questions}


def percentile(values: list[float], q: float) -> float | None:
    """Interpolação linear entre os vizinhos, como o padrão do numpy."""
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    low, high = math.floor(k), math.ceil(k)
    return ordered[low] + (ordered[high] - ordered[low]) * (k - low)


def label_of(ticket: Ticket, question: str) -> str | int | bool | None:
    labels = ticket.labels.model_dump() | ticket.guardrail.model_dump()
    return labels.get(question)


def is_correct(kind: str, value, label) -> bool:
    if value is None:
        return False
    if kind == "noul":
        return (value >= 0.5) == label
    if kind == "score":
        return int(value) == label
    return value == label


def same(kind: str, a, b) -> bool:
    if kind == "noul":
        return (a >= 0.5) == (b >= 0.5)
    return a == b


def f1_macro(pairs: list[tuple[str | None, str]]) -> float:
    classes = {label for _, label in pairs} | {pred for pred, _ in pairs if pred is not None}
    scores = []
    for c in classes:
        tp = sum(pred == c and label == c for pred, label in pairs)
        fp = sum(pred == c and label != c for pred, label in pairs)
        fn = sum(pred != c and label == c for pred, label in pairs)
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0)
    return sum(scores) / len(scores)


def summarize_node(metrics: list[NodeMetric]) -> NodeSummary:
    latencies = [m.latency_ms for m in metrics]
    return NodeSummary(
        calls=len(metrics),
        latency_p50=percentile(latencies, 0.5),
        latency_p95=percentile(latencies, 0.95),
        tokens_in=sum(m.tokens_in for m in metrics),
        tokens_out=sum(m.tokens_out for m in metrics),
        cost_total=sum(m.cost_usd for m in metrics),
        parse_fail_rate=sum(not m.parse_ok for m in metrics) / len(metrics),
        out_of_schema_rate=sum(m.parse_ok and not m.values_in_schema for m in metrics)
        / len(metrics),
        latencies=latencies,
    )


def aggregate(
    batch_id: str, results: list[RunResult], tickets: list[Ticket], config: GraphConfig
) -> BatchReport:
    by_id = {t.id: t for t in tickets}
    # (ticket, node, provider) -> métrica
    calls = {(r.ticket_id, m.node, m.provider): m for r in results for m in r.metrics}
    providers = [p for p in PROVIDERS if any(key[2] == p for key in calls)]

    def answer(ticket_id: str, question: str, provider: str):
        node, _ = QUESTIONS[question]
        metric = calls.get((ticket_id, node, provider))
        if metric is None:
            return None, False  # não foi chamado: fora do denominador
        found = metric.answers.get(question)
        return (found.value if found else None), True

    by_question: dict[str, dict[str, QuestionSummary]] = {}
    agreement: dict[str, float] = {}
    for question, (_, kind) in QUESTIONS.items():
        by_question[question] = {}
        for provider in providers:
            pairs = []
            for result in results:
                value, called = answer(result.ticket_id, question, provider)
                label = label_of(by_id[result.ticket_id], question)
                if called and label is not None:
                    pairs.append((value, label))
            if not pairs and question not in ("segue_politica", "responde_pedido", "promete_fora"):
                continue
            hits = [is_correct(kind, v, label) for v, label in pairs]
            by_question[question][provider] = QuestionSummary(
                n=len(pairs),
                accuracy=sum(hits) / len(hits) if hits else None,
                f1_macro=f1_macro(pairs) if question == "fila" and pairs else None,
                mae=(
                    sum(abs((v if v is not None else 0) - label) for v, label in pairs) / len(pairs)
                    if question == "urgencia" and pairs
                    else None
                ),
            )
        if len(providers) == 2:
            both = [
                (answer(r.ticket_id, question, "jev")[0], answer(r.ticket_id, question, "llm")[0])
                for r in results
            ]
            both = [(a, b) for a, b in both if a is not None and b is not None]
            if both:
                agreement[question] = sum(same(kind, a, b) for a, b in both) / len(both)

    by_node: dict[str, dict[str, NodeSummary]] = {}
    for node in (*NODE_SPECS, "reply"):
        for provider in providers:
            metrics = [m for (_, n, p), m in calls.items() if n == node and p == provider]
            if metrics:
                by_node.setdefault(node, {})[provider] = summarize_node(metrics)

    by_provider = {}
    for provider in providers:
        decisions = [m for (_, n, p), m in calls.items() if p == provider and n in NODE_SPECS]
        accuracies = [
            s[provider].accuracy
            for s in by_question.values()
            if provider in s and s[provider].accuracy is not None
        ]
        cost = sum(m.cost_usd for m in decisions)
        by_provider[provider] = ProviderSummary(
            model=decisions[0].model if decisions else "",
            accuracy=sum(accuracies) / len(accuracies) if accuracies else None,
            cost_total=cost,
            cost_per_1000=cost / len(results) * 1000 if results else 0,
            latency_p95=percentile([m.latency_ms for m in decisions], 0.95),
        )

    rows = []
    for result in results:
        ticket = by_id[result.ticket_id]
        answers, labels, disagrees, wrong = {}, {}, False, False
        for question, (node, kind) in QUESTIONS.items():
            values = {p: answer(result.ticket_id, question, p)[0] for p in providers}
            if all(v is None for v in values.values()):
                continue
            answers[question] = values
            label = label_of(ticket, question)
            if label is not None:
                labels[question] = label
                primary = config.primary_for(node)
                if primary in values and not is_correct(kind, values[primary], label):
                    wrong = True
            if len(providers) == 2 and None not in values.values():
                disagrees |= not same(kind, values["jev"], values["llm"])
        rows.append(
            TicketRow(
                ticket_id=result.ticket_id,
                tags=ticket.tags,
                action=result.action,
                answers=answers,
                labels=labels,
                disagrees=disagrees,
                wrong=wrong,
                has_error=bool(result.errors),
            )
        )

    return BatchReport(
        batch_id=batch_id,
        config_version=config.config_version,
        mode=config.mode,
        llm_model=config.llm_model,
        primary=config.primary,
        n=len(results),
        errors=sum(bool(r.errors) for r in results),
        by_provider=by_provider,
        by_node=by_node,
        by_question=by_question,
        agreement=agreement,
        tickets=rows,
    )
