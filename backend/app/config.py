"""Configuração do grafo, carregada de config/graph.yaml."""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

DecisionNode = Literal["guardrail", "triage", "verify"]
ProviderName = Literal["jev", "llm"]
Probability = Field(ge=0, le=1)


class Thresholds(BaseModel):
    guardrail_block: float = Probability
    triage_min_confidence: float = Probability
    verify_min_policy: float = Probability
    verify_max_overpromise: float = Probability


class CatalogModel(BaseModel):
    label: str
    provider: Literal["openai", "anthropic"]
    model_id: str


class GraphConfig(BaseModel):
    config_version: str
    mode: Literal["replay", "live"]
    primary: ProviderName
    llm_model: str
    providers: dict[DecisionNode, Literal["llm", "jev", "both"]]
    llm_model_overrides: dict[DecisionNode, str] = {}
    thresholds: Thresholds
    catalog: list[CatalogModel] = []

    def providers_for(self, node: str) -> list[ProviderName]:
        mode = self.providers[node]
        return ["jev", "llm"] if mode == "both" else [mode]

    def primary_for(self, node: str) -> ProviderName:
        """O primário global, ou o único provider do node quando o primário não roda nele."""
        available = self.providers_for(node)
        return self.primary if self.primary in available else available[0]

    def llm_model_for(self, node: str) -> str:
        return self.llm_model_overrides.get(node, self.llm_model)


def load_config(path: Path = CONFIG_DIR / "graph.yaml") -> GraphConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if mode := os.environ.get("PROVIDER_MODE"):
        data["mode"] = mode
    return GraphConfig.model_validate(data)
