"""Golden set e política de reembolso, versionados em data/ (PRD 9.3)."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
GOLDEN_SET_PATH = DATA_DIR / "golden_set.json"
POLICY_PATH = DATA_DIR / "policy.md"


class TicketLabels(BaseModel):
    fila: Literal["financeiro", "pedidos", "conta", "outro"]
    urgencia: Literal[0, 1, 2]  # pode esperar, esta semana, hoje
    pede_reembolso: bool
    risco_churn: bool


class GuardrailLabels(BaseModel):
    injection: bool
    dado_sensivel: bool
    fora_escopo: bool


class TicketInput(BaseModel):
    """O que o grafo vê de um ticket. Ticket digitado na interface só tem isto."""

    id: str
    text: str
    channel: Literal["email", "chat", "formulario"] = "formulario"


class Ticket(TicketInput):
    """Ticket do golden set, com os rótulos que servem de gabarito."""

    labels: TicketLabels
    guardrail: GuardrailLabels
    tags: list[str]
    difficulty: Literal["easy", "medium", "hard"]


def load_golden_set(
    tag: str | None = None, limit: int | None = None, path: Path = GOLDEN_SET_PATH
) -> list[Ticket]:
    tickets = [Ticket.model_validate(t) for t in json.loads(path.read_text(encoding="utf-8"))]
    if tag is not None:
        tickets = [t for t in tickets if tag in t.tags]
    return tickets[:limit]


def load_policy(path: Path = POLICY_PATH) -> str:
    return path.read_text(encoding="utf-8")
