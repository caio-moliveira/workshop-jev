"""Reproduz respostas gravadas de execuções reais, com a latência original."""

import asyncio
import json
from pathlib import Path
from typing import Literal

from app.providers.base import NodeSpec, ProviderResult

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "replay"


def llm_fixture_dir(prompt_style: str = "spec") -> str:
    """O LLM com system prompt próprio responde diferente: as gravações ficam separadas."""
    return "llm" if prompt_style == "spec" else "llm-native"


class ReplayMissError(Exception):
    """Não há gravação para a pergunta, o node ou a tool pedida."""


class ReplayProvider:
    def __init__(
        self,
        source: Literal["jev", "llm"],
        simulate_latency: bool = True,
        fixtures_dir: Path = FIXTURES_DIR,
        directory: str | None = None,
    ):
        self.source = source
        self.simulate_latency = simulate_latency
        self.fixtures_dir = fixtures_dir
        self.directory = directory or source

    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult:
        question_id = payload["question_id"]
        path = self.fixtures_dir / self.directory / f"{question_id}.json"
        recorded = load_fixture(path)["nodes"].get(node.name) if path.exists() else None
        if recorded is None:
            raise ReplayMissError(
                f"sem gravação de {self.directory} para a pergunta {question_id}, node {node.name}"
            )

        result = ProviderResult.model_validate(recorded)
        if self.simulate_latency:
            await asyncio.sleep(result.latency_ms / 1000)
        return result


def has_fixture(
    question_id: str, fixtures_dir: Path = FIXTURES_DIR, prompt_style: str = "spec"
) -> bool:
    """Há gravação dos dois providers para a pergunta, no modo de prompt do LLM pedido."""
    dirs = ("jev", llm_fixture_dir(prompt_style))
    return all((fixtures_dir / d / f"{question_id}.json").exists() for d in dirs)


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
