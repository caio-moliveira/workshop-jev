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


async def test_resposta_gravada_para_outra_tool_nao_e_reaproveitada(tmp_path):
    from app.providers.reply import ReplayReplyWriter

    (tmp_path / "llm").mkdir()
    reply = {
        "tool": "kpis",
        "text": "A receita foi R$ 10.",
        "model": "m",
        "latency_ms": 1.0,
        "tokens_in": 1,
        "tokens_out": 1,
        "cost_usd": 0.0,
    }
    fixture = {"question_id": "q-1", "config_version": "2", "nodes": {}, "reply": reply}
    (tmp_path / "llm" / "q-1.json").write_text(json.dumps(fixture), encoding="utf-8")
    writer = ReplayReplyWriter(simulate_latency=False, fixtures_dir=tmp_path)

    written = await writer.write({"question_id": "q-1", "tool": {"name": "kpis"}})
    assert written.text == "A receita foi R$ 10."
    with pytest.raises(ReplayMissError, match="vendas_mensal"):
        await writer.write({"question_id": "q-1", "tool": {"name": "vendas_mensal"}})
