"""O node `reply`: a resposta à pergunta, escrita com os dados da tool. Só LLM (PRD 5)."""

import asyncio
import json
import time
from pathlib import Path
from typing import Protocol

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.metrics.pricing import Pricing, cost_usd
from app.providers.llm import decision_kwargs
from app.providers.replay import FIXTURES_DIR, ReplayMissError, load_fixture

SYSTEM_PROMPT = (
    "Você é analista de vendas da empresa Mercado Jornada. Responda à pergunta em português, "
    "em poucas frases, usando só os dados recebidos da consulta. Cite os números como vieram "
    "(valores em reais), faça no máximo contas simples sobre eles e, se os dados não "
    "responderem à pergunta, diga isso em vez de estimar."
)


class ReplyResult(BaseModel):
    text: str
    model: str
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost_usd: float


class ReplyWriter(Protocol):
    async def write(self, payload: dict) -> ReplyResult: ...


class LLMReplyWriter:
    def __init__(self, model: str, pricing: Pricing, chat_model: BaseChatModel | None = None):
        self.model_id = model.split(":", 1)[-1]
        self.pricing = pricing
        self.chat_model = chat_model or init_chat_model(model, **decision_kwargs(model))

    async def write(self, payload: dict) -> ReplyResult:
        state = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(f"Pergunta e dados:\n{state}")]

        start = time.perf_counter()
        message = await self.chat_model.ainvoke(messages)
        latency_ms = (time.perf_counter() - start) * 1000

        usage = message.usage_metadata or {}
        tokens_in, tokens_out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        return ReplyResult(
            text=message.text,
            model=self.model_id,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd(self.model_id, tokens_in, tokens_out, self.pricing),
        )


class ReplayReplyWriter:
    def __init__(self, simulate_latency: bool = True, fixtures_dir: Path = FIXTURES_DIR):
        self.simulate_latency = simulate_latency
        self.fixtures_dir = fixtures_dir

    async def write(self, payload: dict) -> ReplyResult:
        question_id = payload["question_id"]
        path = self.fixtures_dir / "llm" / f"{question_id}.json"
        recorded = load_fixture(path).get("reply") if path.exists() else None
        if recorded is None:
            raise ReplayMissError(f"sem gravação de reply para a pergunta {question_id}")
        # A resposta depende da consulta: gravada para outra tool, ela citaria outros dados.
        tool = payload["tool"]["name"]
        if recorded.get("tool", tool) != tool:
            raise ReplayMissError(
                f"a resposta gravada para {question_id} usa {recorded['tool']}, não {tool}"
            )

        result = ReplyResult.model_validate(recorded)
        if self.simulate_latency:
            await asyncio.sleep(result.latency_ms / 1000)
        return result
