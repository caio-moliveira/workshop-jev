import json

import pytest
from pydantic import ValidationError

from app.dataset import load_golden_set


def question(id: str, tags: list[str], tool: str = "kpis") -> dict:
    return {
        "id": id,
        "text": "Qual a receita de 2026?",
        "labels": {"tool": tool},
        "guardrail": {"injection": False, "dado_sensivel": False, "fora_escopo": False},
        "tags": tags,
        "difficulty": "medium",
    }


@pytest.fixture
def golden_set(tmp_path):
    path = tmp_path / "golden_set.json"
    questions = [
        question("q-001", ["kpis", "meta"]),
        question("q-002", ["regiao"], tool="vendas_por_regiao"),
        question("q-003", ["vendedor", "meta"], tool="vendas_por_vendedor"),
    ]
    path.write_text(json.dumps(questions), encoding="utf-8")
    return path


def test_filtra_por_tag(golden_set):
    questions = load_golden_set(tag="meta", path=golden_set)

    assert [q.id for q in questions] == ["q-001", "q-003"]


def test_limita_a_quantidade(golden_set):
    questions = load_golden_set(limit=2, path=golden_set)

    assert [q.id for q in questions] == ["q-001", "q-002"]


def test_filtra_e_limita(golden_set):
    questions = load_golden_set(tag="meta", limit=1, path=golden_set)

    assert [q.id for q in questions] == ["q-001"]


def test_aceita_nenhuma_como_tool(tmp_path):
    path = tmp_path / "golden_set.json"
    path.write_text(json.dumps([question("q-001", [], tool="nenhuma")]), encoding="utf-8")

    assert load_golden_set(path=path)[0].labels.tool == "nenhuma"


def test_rejeita_tool_fora_do_registro(tmp_path):
    path = tmp_path / "golden_set.json"
    path.write_text(json.dumps([question("q-001", [], tool="vw_kpis")]), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_golden_set(path=path)
