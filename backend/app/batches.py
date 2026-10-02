"""Execução de lote: N tickets do golden set com concorrência limitada (PRD 11 e 14)."""

import asyncio
import csv
import io
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.config import GraphConfig
from app.dataset import Ticket, load_golden_set
from app.graph import Providers, RunResult, run_ticket
from app.metrics.aggregator import QUESTIONS, BatchReport, aggregate, is_correct, label_of
from app.metrics.pricing import Pricing
from app.providers.replay import FIXTURES_DIR, has_fixture
from app.runs import EventChannel
from app.store import RunStore

MAX_BATCH = 330


class BatchEvent(BaseModel):
    type: Literal["batch.started", "batch.progress", "batch.finished"]
    batch_id: str
    data: dict = {}


def select_tickets(
    config: GraphConfig, n: int, tag: str | None, fixtures_dir: Path = FIXTURES_DIR
) -> list[Ticket]:
    """Em replay, só os tickets que têm gravação."""
    tickets = load_golden_set(tag=tag)
    if config.mode == "replay":
        tickets = [t for t in tickets if has_fixture(t.id, fixtures_dir)]
    return tickets[:n]


def estimate_cost(
    config: GraphConfig, n: int, pricing: Pricing, fixtures_dir: Path = FIXTURES_DIR
) -> float | None:
    """Teto de custo de N tickets passando por todos os nodes, com a média de tokens das
    gravações e os preços atuais. None se não há gravação ou falta preço de algum modelo."""
    tokens: dict[tuple[str, str], list[tuple[int, int]]] = {}
    # Só as gravações dos providers: fixtures_dir/tools/ guarda resultados de tools.
    paths = [p for source in ("jev", "llm") for p in (fixtures_dir / source).glob("*.json")]
    for path in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        for node, result in fixture["nodes"].items():
            tokens.setdefault((node, path.parent.name), []).append(
                (result["tokens_in"], result["tokens_out"])
            )
        if reply := fixture.get("reply"):
            tokens.setdefault(("reply", "llm"), []).append(
                (reply["tokens_in"], reply["tokens_out"])
            )

    calls = [(node, p) for node in config.providers for p in config.providers_for(node)]
    calls.append(("reply", "llm"))
    per_ticket = 0.0
    for node, provider in calls:
        samples = tokens.get((node, provider))
        model = "jev-1.13.0" if provider == "jev" else config.llm_model_for(node).split(":", 1)[-1]
        price = pricing.models.get(model)
        if not samples or price is None or price.input is None or price.output is None:
            return None
        avg_in = sum(s[0] for s in samples) / len(samples)
        avg_out = sum(s[1] for s in samples) / len(samples)
        per_ticket += (avg_in * price.input + avg_out * price.output) / 1_000_000
    return per_ticket * n


async def run_batch(
    batch_id: str,
    tickets: list[Ticket],
    config: GraphConfig,
    providers: Providers,
    store: RunStore,
    channel: EventChannel,
) -> BatchReport:
    async def publish(type: str, data: dict) -> None:
        await channel.publish(BatchEvent(type=type, batch_id=batch_id, data=data))

    await publish(
        "batch.started",
        {"n": len(tickets), "mode": config.mode, "config_version": config.config_version},
    )
    semaphore = asyncio.Semaphore(config.batch_concurrency)
    results: list[RunResult] = []
    failed: list[str] = []

    async def one(ticket: Ticket) -> None:
        async with semaphore:
            try:
                result = await run_ticket(ticket, config, providers=providers)
            except Exception as error:
                # Um ticket que falha conta como erro e não derruba o lote.
                failed.append(ticket.id)
                summary = {"ticket_id": ticket.id, "error": f"{type(error).__name__}: {error}"}
            else:
                results.append(result)
                store.save_run(result, batch_id)
                summary = {
                    "ticket_id": ticket.id,
                    "action": result.action,
                    "has_error": bool(result.errors),
                }
        await publish(
            "batch.progress",
            {"done": len(results) + len(failed), "total": len(tickets), "ticket": summary},
        )

    await asyncio.gather(*(one(t) for t in tickets))

    order = {t.id: i for i, t in enumerate(tickets)}
    results.sort(key=lambda r: order[r.ticket_id])
    report = aggregate(batch_id, results, tickets, config)
    report.errors += len(failed)
    store.save_report(report, batch_id)
    channel.extra["results"] = results
    await publish("batch.finished", report.model_dump(mode="json"))
    await channel.finish(result=report)
    return report


CSV_FIELDS = [
    "batch_id",
    "config_version",
    "mode",
    "ticket_id",
    "node",
    "question",
    "provider",
    "model",
    "is_primary",
    "value",
    "confidence",
    "label",
    "correct",
    "latency_ms",
    "tokens_in",
    "tokens_out",
    "cost_usd",
]


def export_csv(report: BatchReport, results: list[RunResult]) -> str:
    """Uma linha por ticket, provider e pergunta. Latência, tokens e custo são do node."""
    tickets = {t.id: t for t in load_golden_set()}
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for result in results:
        ticket = tickets.get(result.ticket_id)
        for metric in result.metrics:
            if metric.node == "reply":
                continue
            for question, (node, kind) in QUESTIONS.items():
                if node != metric.node:
                    continue
                answer = metric.answers.get(question)
                value = answer.value if answer else None
                label = label_of(ticket, question) if ticket else None
                writer.writerow(
                    {
                        "batch_id": report.batch_id,
                        "config_version": report.config_version,
                        "mode": report.mode,
                        "ticket_id": result.ticket_id,
                        "node": node,
                        "question": question,
                        "provider": metric.provider,
                        "model": metric.model,
                        "is_primary": metric.is_primary,
                        "value": value,
                        "confidence": answer.confidence if answer else None,
                        "label": label,
                        "correct": is_correct(kind, value, label) if label is not None else None,
                        "latency_ms": metric.latency_ms,
                        "tokens_in": metric.tokens_in,
                        "tokens_out": metric.tokens_out,
                        "cost_usd": metric.cost_usd,
                    }
                )
    return output.getvalue()
