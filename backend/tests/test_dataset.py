import json

import pytest
from pydantic import ValidationError

from app.dataset import load_golden_set, load_policy


def ticket(id: str, tags: list[str], **labels) -> dict:
    return {
        "id": id,
        "text": "Fui cobrado duas vezes no pedido A-104.",
        "channel": "email",
        "labels": {
            "fila": "financeiro",
            "urgencia": 2,
            "pede_reembolso": True,
            "risco_churn": False,
        }
        | labels,
        "guardrail": {"injection": False, "dado_sensivel": False, "fora_escopo": False},
        "tags": tags,
        "difficulty": "medium",
    }


@pytest.fixture
def golden_set(tmp_path):
    path = tmp_path / "golden_set.json"
    tickets = [
        ticket("tk-0001", ["cobranca-duplicada", "churn"]),
        ticket("tk-0002", ["rastreamento"]),
        ticket("tk-0003", ["atraso-entrega", "churn"]),
    ]
    path.write_text(json.dumps(tickets), encoding="utf-8")
    return path


def test_filtra_por_tag(golden_set):
    tickets = load_golden_set(tag="churn", path=golden_set)

    assert [t.id for t in tickets] == ["tk-0001", "tk-0003"]


def test_limita_a_quantidade(golden_set):
    tickets = load_golden_set(limit=2, path=golden_set)

    assert [t.id for t in tickets] == ["tk-0001", "tk-0002"]


def test_filtra_e_limita(golden_set):
    tickets = load_golden_set(tag="churn", limit=1, path=golden_set)

    assert [t.id for t in tickets] == ["tk-0001"]


def test_rejeita_fila_fora_das_opcoes(tmp_path):
    path = tmp_path / "golden_set.json"
    path.write_text(json.dumps([ticket("tk-0001", [], fila="suporte")]), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_golden_set(path=path)


def test_rejeita_urgencia_fora_da_escala(tmp_path):
    path = tmp_path / "golden_set.json"
    path.write_text(json.dumps([ticket("tk-0001", [], urgencia=3)]), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_golden_set(path=path)


def test_carrega_a_politica_de_reembolso():
    assert "reembolso" in load_policy().lower()
