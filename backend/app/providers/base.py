"""Contratos compartilhados por todos os providers (PRD 7.2 e 7.3)."""

from typing import Literal, Protocol

from pydantic import BaseModel


class DecisionSpec(BaseModel):
    name: str
    type: Literal["choice", "score", "noul"]
    instructions: str
    criteria: dict | list | None = None


class NodeSpec(BaseModel):
    name: str
    state_fields: list[str]
    questions: list[DecisionSpec]


class Answer(BaseModel):
    value: str | int | float  # choice: opção; score: nível; noul: probabilidade
    confidence: float | None = None  # Jev: calibrada; LLM: autorrelatada
    probabilities: dict | None = None  # Jev: distribuição; LLM: None


class ProviderResult(BaseModel):
    provider: Literal["jev", "llm", "replay"]
    model: str
    answers: dict[str, Answer]
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost_usd: float
    parse_ok: bool
    values_in_schema: bool
    raw: dict


class DecisionProvider(Protocol):
    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult: ...
