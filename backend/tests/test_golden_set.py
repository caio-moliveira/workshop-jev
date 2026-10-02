"""Contrato do golden set versionado em data/golden_set.json (PRD 9.3, SPEC-09)."""

from collections import Counter

import pytest

from app.dataset import load_golden_set
from app.tools import NO_TOOL, TOOLS


@pytest.fixture(scope="module")
def questions():
    return load_golden_set()


def test_tem_60_perguntas_e_20_adversariais(questions):
    ids = [q.id for q in questions]

    assert len(ids) == 80
    assert len(set(ids)) == 80
    assert sum(i.startswith("q-") for i in ids) == 60
    assert sum(i.startswith("adv-") for i in ids) == 20


def test_nenhum_texto_vazio_nem_repetido(questions):
    texts = [q.text.strip() for q in questions]

    assert all(texts)
    assert len(set(texts)) == len(texts)


def test_cada_tool_e_nenhuma_tem_pelo_menos_6_perguntas(questions):
    tools = Counter(q.labels.tool for q in questions if q.id.startswith("q-"))

    assert set(tools) == {*TOOLS, NO_TOOL}
    assert min(tools.values()) >= 6


def test_adversariais_cobrem_os_tres_riscos(questions):
    adversarial = [q for q in questions if q.id.startswith("adv-")]

    for risco in ("injection", "dado_sensivel", "fora_escopo"):
        assert sum(getattr(q.guardrail, risco) for q in adversarial) >= 6
    assert all(any(q.guardrail.model_dump().values()) for q in adversarial)


def test_perguntas_de_vendas_nao_disparam_o_guardrail(questions):
    sales = [q for q in questions if q.id.startswith("q-")]

    assert not any(any(q.guardrail.model_dump().values()) for q in sales)


def test_tem_casos_de_fronteira(questions):
    assert sum("fronteira" in q.tags for q in questions) >= 10
