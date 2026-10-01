import json

import pytest
from typesafe_sdk import SystemOneResponse

from app.metrics.pricing import Pricing
from app.providers.jev import JevProvider
from app.specs import NODE_SPECS, TRIAGE

PRICING = Pricing.model_validate(
    {"reference_date": "x", "source": "x", "models": {"jev-1.13.0": {"input": 0.042, "output": 0}}}
)

TRIAGE_RESPONSE = {
    "model": "jev-1.13.0",
    "usage": {"input_tokens": 1000, "output_tokens": 4},
    "answers": {
        "fila": {
            "type": "choice",
            "choice": "financeiro",
            "confidence": 0.91,
            "probabilities": {"financeiro": 0.91, "pedidos": 0.06, "conta": 0.02, "outro": 0.01},
        },
        "urgencia": {
            "type": "score",
            "score": 1.6,
            "confidence": 0.7,
            "legend": {"0": "Pode esperar.", "1": "Esta semana.", "2": "Hoje."},
            "probabilities": {"0": 0.1, "1": 0.2, "2": 0.7},
        },
        "pede_reembolso": {"type": "noul", "noul": 0.97},
        "risco_churn": {"type": "noul", "noul": 0.08},
    },
}


class FakeClient:
    """Cliente do typesafe-sdk que guarda a chamada e devolve uma resposta fixa."""

    def __init__(self, response: dict):
        self.response = response
        self.calls: list[dict] = []

    async def system_one(self, state, questions, *, model=None):
        self.calls.append({"state": state, "questions": questions, "model": model})
        # o SDK decodifica o corpo HTTP em modo estrito, a partir do JSON
        return SystemOneResponse.model_validate_json(json.dumps(self.response))


async def test_mapeia_choice_score_e_noul():
    provider = JevProvider(PRICING, client=FakeClient(TRIAGE_RESPONSE))

    result = await provider.decide(TRIAGE, {"ticket": {"text": "..."}})

    fila = result.answers["fila"]
    assert (fila.value, fila.confidence) == ("financeiro", 0.91)
    assert fila.probabilities["pedidos"] == 0.06
    urgencia = result.answers["urgencia"]
    assert (urgencia.value, urgencia.confidence) == (2, 0.7)
    assert urgencia.probabilities == {"0": 0.1, "1": 0.2, "2": 0.7}
    reembolso = result.answers["pede_reembolso"]
    assert (reembolso.value, reembolso.confidence, reembolso.probabilities) == (0.97, None, None)


async def test_registra_tokens_custo_e_flags():
    provider = JevProvider(PRICING, client=FakeClient(TRIAGE_RESPONSE))

    result = await provider.decide(TRIAGE, {"ticket": {"text": "..."}})

    assert result.provider == "jev"
    assert result.model == "jev-1.13.0"
    assert (result.tokens_in, result.tokens_out) == (1000, 4)
    assert result.cost_usd == pytest.approx(0.000042)
    assert result.parse_ok and result.values_in_schema
    assert result.latency_ms >= 0
    assert result.raw["answers"]["pede_reembolso"]["noul"] == 0.97


@pytest.mark.parametrize("node", NODE_SPECS.values(), ids=lambda n: n.name)
async def test_envia_exatamente_as_perguntas_do_spec(node):
    client = FakeClient({"model": "jev-1.13.0", "usage": {}, "answers": {}})
    payload = {"ticket": {"text": "Quero meu dinheiro de volta"}}

    await JevProvider(PRICING, client=client).decide(node, payload)

    call = client.calls[0]
    assert call["state"] == payload
    assert call["model"] == "jev-1.13.0"
    assert call["questions"] == {
        q.name: {"type": q.type, "instructions": q.instructions, "criteria": q.criteria}
        for q in node.questions
    }
