import json
import time

import pytest

from app.providers.base import NodeSpec, ProviderResult
from app.providers.replay import ReplayMissError, ReplayProvider

TRIAGE = NodeSpec(name="triage", state_fields=["question"], questions=[])
VERIFY = NodeSpec(name="verify", state_fields=["question"], questions=[])

RECORDED = {
    "provider": "jev",
    "model": "jev-1.13.0",
    "answers": {
        "fila": {
            "value": "financeiro",
            "confidence": 0.93,
            "probabilities": {"financeiro": 0.93, "pedidos": 0.05, "conta": 0.01, "outro": 0.01},
        },
        "urgencia": {
            "value": 2,
            "confidence": 0.81,
            "probabilities": {"0": 0.04, "1": 0.15, "2": 0.81},
        },
        "pede_reembolso": {"value": 0.97},
    },
    "latency_ms": 50.0,
    "tokens_in": 412,
    "tokens_out": 9,
    "cost_usd": 0.0000173,
    "parse_ok": True,
    "values_in_schema": True,
    "raw": {"model": "jev-1.13.0"},
}


@pytest.fixture
def fixtures_dir(tmp_path):
    (tmp_path / "jev").mkdir()
    fixture = {"question_id": "q-0042", "config_version": "2", "nodes": {"triage": RECORDED}}
    (tmp_path / "jev" / "q-0042.json").write_text(json.dumps(fixture), encoding="utf-8")
    return tmp_path


async def test_devolve_o_resultado_gravado(fixtures_dir):
    provider = ReplayProvider("jev", simulate_latency=False, fixtures_dir=fixtures_dir)

    result = await provider.decide(TRIAGE, {"question_id": "q-0042"})

    assert result == ProviderResult.model_validate(RECORDED)
    assert result.provider == "jev"
    assert result.answers["urgencia"].value == 2


async def test_pergunta_sem_fixture_cita_pergunta_e_node(fixtures_dir):
    provider = ReplayProvider("jev", simulate_latency=False, fixtures_dir=fixtures_dir)

    with pytest.raises(ReplayMissError, match=r"q-9999.*triage"):
        await provider.decide(TRIAGE, {"question_id": "q-9999"})


async def test_node_sem_fixture_cita_pergunta_e_node(fixtures_dir):
    provider = ReplayProvider("jev", simulate_latency=False, fixtures_dir=fixtures_dir)

    with pytest.raises(ReplayMissError, match=r"q-0042.*verify"):
        await provider.decide(VERIFY, {"question_id": "q-0042"})


async def test_simula_a_latencia_gravada(fixtures_dir):
    provider = ReplayProvider("jev", simulate_latency=True, fixtures_dir=fixtures_dir)

    start = time.perf_counter()
    await provider.decide(TRIAGE, {"question_id": "q-0042"})

    assert (time.perf_counter() - start) * 1000 >= 50
