"""Linha de comando do grafo.

    uv run python -m app.cli run --limit 3                 # usa o mode de graph.yaml / PROVIDER_MODE
    uv run python -m app.cli run --question q-001
    uv run python -m app.cli snapshot                      # banco: grava fixtures/replay/tools/
    uv run --env-file ../.env python -m app.cli record     # live: snapshot + fixtures/replay/

Em replay, `run` só considera as perguntas que têm gravação.
"""

import argparse
import asyncio
import json
import os
import sys

from app.config import GraphConfig, load_config
from app.dataset import Question, load_golden_set
from app.graph import RunResult, run_question
from app.providers.replay import FIXTURES_DIR, has_fixture
from app.tools import TOOLS, PostgresToolRunner, write_tool_fixture

DECISION_NODES = ("guardrail", "triage", "verify")
KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def main(argv: list[str] | None = None) -> int:
    # O console do Windows usa cp1252 por padrão e não imprime acentos nem setas.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="executa perguntas e imprime um resumo")
    run.add_argument("--question")
    run.add_argument("--limit", type=int)
    run.add_argument("--no-latency", action="store_true", help="replay sem esperar a latência")
    record = commands.add_parser("record", help="executa em live e grava as fixtures")
    record.add_argument("--limit", type=int)
    record.add_argument("--concurrency", type=int, default=5)
    commands.add_parser("snapshot", help="lê as views do banco e grava o replay das tools")
    args = parser.parse_args(argv)

    if args.command == "snapshot":
        return asyncio.run(snapshot_command())
    config = load_config()
    if args.command == "run":
        return asyncio.run(run_command(config, args.question, args.limit, not args.no_latency))
    return asyncio.run(record_command(config, args.limit, args.concurrency))


async def run_command(
    config: GraphConfig, question_id: str | None, limit: int | None, latency: bool
) -> int:
    questions = load_golden_set()
    if question_id:
        questions = [q for q in questions if q.id == question_id]
    if config.mode == "replay":
        missing = [q.id for q in questions if not has_fixture(q.id)]
        if question_id and missing:
            print(f"sem gravação de replay para {question_id}", file=sys.stderr)
            return 1
        questions = [q for q in questions if has_fixture(q.id)]
    questions = questions[:limit]
    if not questions:
        print("nenhuma pergunta para executar", file=sys.stderr)
        return 1

    failed = False
    for question in questions:
        result = await run_question(question, config, simulate_latency=latency)
        print(summary(result))
        failed |= bool(result.errors)
    return 1 if failed else 0


def summary(result: RunResult) -> str:
    calls = ", ".join(
        f"{m.node}/{m.provider} {m.latency_ms:.0f}ms" for m in result.metrics if m.node != "reply"
    )
    tool = f"  tool={result.tool_result.tool}" if result.tool_result else ""
    line = f"{result.question_id}  {result.action:<7}  {' → '.join(result.path)}{tool}  [{calls}]"
    if result.reason:
        line += f"\n  motivo: {result.reason}"
    return line + "".join(f"\n  erro: {e}" for e in result.errors)


async def snapshot_command() -> int:
    """Grava o resultado de cada tool. Precisa só do banco, não de chaves."""
    runner = PostgresToolRunner()
    try:
        for name in TOOLS:
            result = await runner.run(name)
            path = write_tool_fixture(result)
            print(f"{name}: {result.row_count} linhas → {path.relative_to(FIXTURES_DIR.parent)}")
    except OSError as error:
        print(f"banco fora do ar ({error}); rode docker compose up -d --wait", file=sys.stderr)
        return 1
    finally:
        await runner.close()
    return 0


async def record_command(config: GraphConfig, limit: int | None, concurrency: int) -> int:
    if config.mode != "live":
        print("record exige PROVIDER_MODE=live", file=sys.stderr)
        return 1
    llm_provider = config.llm_model.split(":", 1)[0]
    needed = ["TYPESAFE_API_KEY", KEYS.get(llm_provider, "")]
    missing = [key for key in needed if not os.environ.get(key)]
    if missing:
        print(f"faltam chaves no ambiente: {', '.join(missing)}", file=sys.stderr)
        return 1
    # As tools vêm do banco atual: o replay e as respostas gravadas citam os mesmos números.
    if await snapshot_command() != 0:
        return 1

    # Grava os dois providers em todos os nodes, para o replay servir a qualquer configuração.
    config = config.model_copy(update={"providers": dict.fromkeys(DECISION_NODES, "both")})
    questions = load_golden_set()[:limit]
    semaphore = asyncio.Semaphore(concurrency)

    async def one(question: Question) -> bool:
        async with semaphore:
            result = await run_question(question, config)
        write_fixtures(result, config)
        print(summary(result))
        return not result.errors

    results = await asyncio.gather(*(one(q) for q in questions))
    return 0 if all(results) else 1


def write_fixtures(result: RunResult, config: GraphConfig) -> None:
    for source in ("jev", "llm"):
        nodes = {
            m.node: m.model_dump(mode="json", exclude={"node", "is_primary"})
            for m in result.metrics
            if m.provider == source and m.node in DECISION_NODES
        }
        fixture = {
            "question_id": result.question_id,
            "config_version": config.config_version,
            "nodes": nodes,
        }
        reply = next((m for m in result.metrics if m.node == "reply"), None)
        if source == "llm" and reply is not None:
            fixture["reply"] = {
                "tool": result.tool_result.tool,
                "text": reply.raw["text"],
                "model": reply.model,
                "latency_ms": reply.latency_ms,
                "tokens_in": reply.tokens_in,
                "tokens_out": reply.tokens_out,
                "cost_usd": reply.cost_usd,
            }
        path = FIXTURES_DIR / source / f"{result.question_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
