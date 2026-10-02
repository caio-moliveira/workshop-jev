"""Execução de lote: N perguntas do golden set com concorrência limitada (PRD 11 e 14)."""

import asyncio
import csv
import io
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.config import GraphConfig
from app.dataset import Question, load_golden_set
from app.graph import Providers, RunResult, run_question
from app.metrics.aggregator import QUESTIONS, BatchReport, aggregate, is_correct, label_of
from app.metrics.pricing import Pricing
from app.providers.replay import FIXTURES_DIR, has_fixture, llm_fixture_dir
from app.runs import EventChannel
from app.store import RunStore

MAX_BATCH = 100


class BatchEvent(BaseModel):
    type: Literal["batch.started", "batch.progress", "batch.finished"]
    batch_id: str
    data: dict = {}


def select_questions(
    config: GraphConfig, n: int, tag: str | None, fixtures_dir: Path = FIXTURES_DIR
) -> list[Question]:
    """Em replay, só as perguntas que têm gravação."""
    questions = load_golden_set(tag=tag)
    if config.mode == "replay":
        style = config.llm_prompt_style
        questions = [q for q in questions if has_fixture(q.id, fixtures_dir, style)]
    return questions[:n]


def estimate_cost(
    config: GraphConfig, n: int, pricing: Pricing, fixtures_dir: Path = FIXTURES_DIR
) -> float | None:
    """Teto de custo de N perguntas passando por todos os nodes, com a média de tokens das
    gravações e os preços atuais. None se não há gravação ou falta preço de algum modelo."""
    tokens: dict[tuple[str, str], list[tuple[int, int]]] = {}
    # Só as gravações dos providers: fixtures_dir/tools/ guarda resultados de tools.
    dirs = {"jev": "jev", "llm": llm_fixture_dir(config.llm_prompt_style)}
    paths = [
        (p, provider) for provider, d in dirs.items() for p in (fixtures_dir / d).glob("*.json")
    ]
    for path, provider in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        for node, result in fixture["nodes"].items():
            tokens.setdefault((node, provider), []).append(
                (result["tokens_in"], result["tokens_out"])
            )
        if reply := fixture.get("reply"):
            tokens.setdefault(("reply", "llm"), []).append(
                (reply["tokens_in"], reply["tokens_out"])
            )

    calls = [(node, p) for node in config.providers for p in config.providers_for(node)]
    calls.append(("reply", "llm"))
    per_question = 0.0
    for node, provider in calls:
        samples = tokens.get((node, provider))
        model = "jev-1.13.0" if provider == "jev" else config.llm_model_for(node).split(":", 1)[-1]
        price = pricing.models.get(model)
        if not samples or price is None or price.input is None or price.output is None:
            return None
        avg_in = sum(s[0] for s in samples) / len(samples)
        avg_out = sum(s[1] for s in samples) / len(samples)
        per_question += (avg_in * price.input + avg_out * price.output) / 1_000_000
    return per_question * n


async def run_batch(
    batch_id: str,
    questions: list[Question],
    config: GraphConfig,
    providers: Providers,
    store: RunStore,
    channel: EventChannel,
) -> BatchReport:
    async def publish(type: str, data: dict) -> None:
        await channel.publish(BatchEvent(type=type, batch_id=batch_id, data=data))

    await publish(
        "batch.started",
        {"n": len(questions), "mode": config.mode, "config_version": config.config_version},
    )
    semaphore = asyncio.Semaphore(config.batch_concurrency)
    results: list[RunResult] = []
    failed: list[str] = []

    async def one(question: Question) -> None:
        async with semaphore:
            try:
                result = await run_question(question, config, providers=providers)
            except Exception as error:
                # Uma pergunta que falha conta como erro e não derruba o lote.
                failed.append(question.id)
                summary = {"question_id": question.id, "error": f"{type(error).__name__}: {error}"}
            else:
                results.append(result)
                store.save_run(result, batch_id)
                summary = {
                    "question_id": question.id,
                    "action": result.action,
                    "has_error": bool(result.errors),
                }
        await publish(
            "batch.progress",
            {"done": len(results) + len(failed), "total": len(questions), "question": summary},
        )

    await asyncio.gather(*(one(q) for q in questions))

    order = {q.id: i for i, q in enumerate(questions)}
    results.sort(key=lambda r: order[r.question_id])
    report = aggregate(batch_id, results, questions, config)
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
    "question_id",
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
    """Uma linha por pergunta do golden set, provider e pergunta de decisão. Latência,
    tokens e custo são do node."""
    golden = {q.id: q for q in load_golden_set()}
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for result in results:
        item = golden.get(result.question_id)
        for metric in result.metrics:
            if metric.node == "reply":
                continue
            for question, (node, kind) in QUESTIONS.items():
                if node != metric.node:
                    continue
                answer = metric.answers.get(question)
                value = answer.value if answer else None
                label = label_of(item, question) if item else None
                writer.writerow(
                    {
                        "batch_id": report.batch_id,
                        "config_version": report.config_version,
                        "mode": report.mode,
                        "question_id": result.question_id,
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
