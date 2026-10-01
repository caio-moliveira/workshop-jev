"""Chamadas reais, para o apresentador validar as chaves. Fora da CI.

cd backend && uv run --env-file ../.env pytest -m live
"""

import os

import pytest

from app.metrics.pricing import load_pricing
from app.providers.jev import JevProvider
from app.providers.llm import LLMProvider
from app.specs import TRIAGE

pytestmark = pytest.mark.live

PAYLOAD = {
    "ticket": {"text": "Fui cobrado duas vezes no pedido A-104. Quero o estorno hoje ou cancelo."},
    "policy": "Cobrança duplicada: estorno integral do valor cobrado a mais, sempre.",
}


def require(key: str) -> None:
    if not os.environ.get(key):
        pytest.skip(f"{key} não definida")


async def test_jev_de_verdade():
    require("TYPESAFE_API_KEY")

    result = await JevProvider(load_pricing()).decide(TRIAGE, PAYLOAD)

    assert result.answers["fila"].value == "financeiro"
    assert result.tokens_in > 0


async def test_llm_de_verdade():
    require("OPENAI_API_KEY")

    result = await LLMProvider("openai:gpt-5.6-luna", load_pricing()).decide(TRIAGE, PAYLOAD)

    assert result.parse_ok
    assert result.answers["fila"].value == "financeiro"
    assert result.tokens_in > 0
