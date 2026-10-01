import pytest

from app.metrics.pricing import Pricing, PricingMissingError, cost_usd, load_pricing

PRICING = Pricing.model_validate(
    {
        "reference_date": "2026-10-02",
        "source": "teste",
        "models": {
            "gpt-5.6-luna": {"input": 0.20, "output": 1.20},
            "jev-1.13.0": {"input": 0.042, "output": 0},
            "claude-haiku-4-5-20251001": {"input": None, "output": None},
        },
    }
)


def test_custo_de_um_milhao_de_tokens_de_entrada_e_saida():
    assert cost_usd("gpt-5.6-luna", 1_000_000, 1_000_000, PRICING) == pytest.approx(1.40)


def test_saida_do_jev_nao_custa():
    assert cost_usd("jev-1.13.0", 1_000_000, 500_000, PRICING) == pytest.approx(0.042)


def test_modelo_fora_da_tabela_e_erro():
    with pytest.raises(PricingMissingError, match="gpt-9"):
        cost_usd("gpt-9", 10, 10, PRICING)


def test_modelo_sem_preco_preenchido_e_erro():
    with pytest.raises(PricingMissingError, match="claude-haiku"):
        cost_usd("claude-haiku-4-5-20251001", 10, 10, PRICING)


def test_tabela_versionada_tem_data_fonte_e_os_nove_modelos():
    pricing = load_pricing()

    assert pricing.reference_date
    assert pricing.source
    assert set(pricing.models) == {
        "gpt-6-sol",
        "gpt-6-luna",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-haiku-4-5-20251001",
        "jev-1.13.0",
    }
    assert pricing.models["jev-1.13.0"].input == pytest.approx(0.042)
    assert pricing.models["jev-1.13.0"].output == 0
