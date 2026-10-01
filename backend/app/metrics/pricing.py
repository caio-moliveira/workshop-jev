"""Tabela de preços por modelo, versionada em config/pricing.yaml (PRD 7.7 e 9.1)."""

from pathlib import Path

import yaml
from pydantic import BaseModel

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class ModelPrice(BaseModel):
    input: float | None  # US$ por 1M tokens; None enquanto não preenchido
    output: float | None


class Pricing(BaseModel):
    reference_date: str
    source: str
    models: dict[str, ModelPrice]


class PricingMissingError(Exception):
    """O modelo não está na tabela ou está sem preço preenchido."""


def load_pricing(path: Path = CONFIG_DIR / "pricing.yaml") -> Pricing:
    return Pricing.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def cost_usd(model: str, tokens_in: int, tokens_out: int, pricing: Pricing) -> float:
    price = pricing.models.get(model)
    if price is None or price.input is None or price.output is None:
        raise PricingMissingError(f"sem preço para {model} em config/pricing.yaml")
    return (tokens_in * price.input + tokens_out * price.output) / 1_000_000
