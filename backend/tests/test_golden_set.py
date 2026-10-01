"""Contrato do golden set versionado em data/golden_set.json (PRD 9.3)."""

from collections import Counter

import pytest

from app.dataset import load_golden_set


@pytest.fixture(scope="module")
def tickets():
    return load_golden_set()


def test_tem_300_tickets_e_30_adversariais(tickets):
    ids = [t.id for t in tickets]

    assert len(ids) == 330
    assert len(set(ids)) == 330
    assert sum(i.startswith("tk-") for i in ids) == 300
    assert sum(i.startswith("adv-") for i in ids) == 30


def test_nenhum_texto_vazio(tickets):
    assert all(t.text.strip() for t in tickets)


def test_cada_fila_tem_pelo_menos_40_tickets(tickets):
    filas = Counter(t.labels.fila for t in tickets if t.id.startswith("tk-"))

    assert set(filas) == {"financeiro", "pedidos", "conta", "outro"}
    assert min(filas.values()) >= 40


def test_cada_nivel_de_urgencia_tem_pelo_menos_60_tickets(tickets):
    niveis = Counter(t.labels.urgencia for t in tickets if t.id.startswith("tk-"))

    assert set(niveis) == {0, 1, 2}
    assert min(niveis.values()) >= 60


def test_adversariais_cobrem_os_tres_riscos(tickets):
    adversarial = [t for t in tickets if t.id.startswith("adv-")]

    for risco in ("injection", "dado_sensivel", "fora_escopo"):
        assert sum(getattr(t.guardrail, risco) for t in adversarial) >= 8


def test_tickets_de_triagem_nao_disparam_o_guardrail(tickets):
    triagem = [t for t in tickets if t.id.startswith("tk-")]

    assert not any(any(t.guardrail.model_dump().values()) for t in triagem)
