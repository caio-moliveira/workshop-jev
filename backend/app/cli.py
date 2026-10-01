"""Linha de comando do grafo.

    uv run python -m app.cli run --limit 3                 # usa o mode de graph.yaml / PROVIDER_MODE
    uv run python -m app.cli run --ticket tk-0042
    uv run --env-file ../.env python -m app.cli record     # live: grava fixtures/replay/

Em replay, `run` só considera os tickets que têm gravação.
"""

import argparse
import asyncio
import json
import os
import sys

from app.config import GraphConfig, load_config
from app.dataset import Ticket, load_golden_set
from app.graph import RunResult, run_ticket
from app.providers.replay import FIXTURES_DIR, has_fixture

DECISION_NODES = ("guardrail", "triage", "verify")
KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def main(argv: list[str] | None = None) -> int:
    # O console do Windows usa cp1252 por padrão e não imprime acentos nem setas.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="executa tickets e imprime um resumo")
    run.add_argument("--ticket")
    run.add_argument("--limit", type=int)
    run.add_argument("--no-latency", action="store_true", help="replay sem esperar a latência")
    record = commands.add_parser("record", help="executa em live e grava as fixtures")
    record.add_argument("--limit", type=int)
    record.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args(argv)

    config = load_config()
    if args.command == "run":
        return asyncio.run(run_command(config, args.ticket, args.limit, not args.no_latency))
    return asyncio.run(record_command(config, args.limit, args.concurrency))


async def run_command(
    config: GraphConfig, ticket_id: str | None, limit: int | None, latency: bool
) -> int:
    tickets = load_golden_set()
    if ticket_id:
        tickets = [t for t in tickets if t.id == ticket_id]
    if config.mode == "replay":
        missing = [t.id for t in tickets if not has_fixture(t.id)]
        if ticket_id and missing:
            print(f"sem gravação de replay para {ticket_id}", file=sys.stderr)
            return 1
        tickets = [t for t in tickets if has_fixture(t.id)]
    tickets = tickets[:limit]
    if not tickets:
        print("nenhum ticket para executar", file=sys.stderr)
        return 1

    failed = False
    for ticket in tickets:
        result = await run_ticket(ticket, config, simulate_latency=latency)
        print(summary(result))
        failed |= bool(result.errors)
    return 1 if failed else 0


def summary(result: RunResult) -> str:
    calls = ", ".join(
        f"{m.node}/{m.provider} {m.latency_ms:.0f}ms" for m in result.metrics if m.node != "reply"
    )
    line = f"{result.ticket_id}  {result.action:<7}  {' → '.join(result.path)}  [{calls}]"
    return line + "".join(f"\n  erro: {e}" for e in result.errors)


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

    # Grava os dois providers em todos os nodes, para o replay servir a qualquer configuração.
    config = config.model_copy(update={"providers": dict.fromkeys(DECISION_NODES, "both")})
    tickets = load_golden_set()[:limit]
    semaphore = asyncio.Semaphore(concurrency)

    async def one(ticket: Ticket) -> bool:
        async with semaphore:
            result = await run_ticket(ticket, config)
        write_fixtures(result, config)
        print(summary(result))
        return not result.errors

    results = await asyncio.gather(*(one(t) for t in tickets))
    return 0 if all(results) else 1


def write_fixtures(result: RunResult, config: GraphConfig) -> None:
    for source in ("jev", "llm"):
        nodes = {
            m.node: m.model_dump(mode="json", exclude={"node", "is_primary"})
            for m in result.metrics
            if m.provider == source and m.node in DECISION_NODES
        }
        fixture = {
            "ticket_id": result.ticket_id,
            "config_version": config.config_version,
            "nodes": nodes,
        }
        reply = next((m for m in result.metrics if m.node == "reply"), None)
        if source == "llm" and reply is not None:
            fixture["reply"] = {
                "text": reply.raw["text"],
                "model": reply.model,
                "latency_ms": reply.latency_ms,
                "tokens_in": reply.tokens_in,
                "tokens_out": reply.tokens_out,
                "cost_usd": reply.cost_usd,
            }
        path = FIXTURES_DIR / source / f"{result.ticket_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
