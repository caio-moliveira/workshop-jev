"""Golden set de perguntas de vendas, versionado em data/ (PRD 9.3)."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator

from app.tools import NO_TOOL, TOOLS

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
GOLDEN_SET_PATH = DATA_DIR / "golden_set.json"


class QuestionLabels(BaseModel):
    tool: str  # uma das tools de TOOLS, ou "nenhuma"

    @field_validator("tool")
    @classmethod
    def known_tool(cls, value: str) -> str:
        if value not in TOOLS and value != NO_TOOL:
            raise ValueError(f"tool fora do registro: {value!r}")
        return value


class GuardrailLabels(BaseModel):
    injection: bool
    dado_sensivel: bool
    fora_escopo: bool


class QuestionInput(BaseModel):
    """O que o grafo vê de uma pergunta. Pergunta digitada na interface só tem isto."""

    id: str
    text: str


class Question(QuestionInput):
    """Pergunta do golden set, com os rótulos que servem de gabarito."""

    labels: QuestionLabels
    guardrail: GuardrailLabels
    tags: list[str]
    difficulty: Literal["easy", "medium", "hard"]


def load_golden_set(
    tag: str | None = None, limit: int | None = None, path: Path = GOLDEN_SET_PATH
) -> list[Question]:
    questions = [Question.model_validate(q) for q in json.loads(path.read_text(encoding="utf-8"))]
    if tag is not None:
        questions = [q for q in questions if tag in q.tags]
    return questions[:limit]
