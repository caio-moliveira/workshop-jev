"""Reproduz respostas gravadas de execuções reais, com a latência original."""

import asyncio
import json
from pathlib import Path
from typing import Literal

from app.providers.base import NodeSpec, ProviderResult

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "replay"


class ReplayMissError(Exception):
    """Não há gravação para a pergunta, o node ou a tool pedida."""


class ReplayProvider:
    def __init__(
        self,
        source: Literal["jev", "llm"],
        simulate_latency: bool = True,
        fixtures_dir: Path = FIXTURES_DIR,
    ):
        self.source = source
        self.simulate_latency = simulate_latency
        self.fixtures_dir = fixtures_dir

    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult:
        question_id = payload["question_id"]
        path = self.fixtures_dir / self.source / f"{question_id}.json"
        recorded = load_fixture(path)["nodes"].get(node.name) if path.exists() else None
        if recorded is None:
            raise ReplayMissError(
                f"sem gravação de {self.source} para a pergunta {question_id}, node {node.name}"
            )

        result = ProviderResult.model_validate(recorded)
        if self.simulate_latency:
            await asyncio.sleep(result.latency_ms / 1000)
        return result


def has_fixture(question_id: str, fixtures_dir: Path = FIXTURES_DIR) -> bool:
    """Há gravação dos dois providers para a pergunta."""
    return all((fixtures_dir / s / f"{question_id}.json").exists() for s in ("jev", "llm"))


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
