"""O node `reply`: rascunho de resposta ao cliente. Só LLM (PRD 5)."""

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
    "Você é atendente da loja Mercado Jornada. Escreva um rascunho curto de resposta ao "
    "cliente, em português, cordial e direto. Siga estritamente a política recebida: não "
    "prometa prazo, valor ou compensação que ela não preveja."
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
        messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(f"Estado:\n{state}")]

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
        ticket_id = payload["ticket_id"]
        path = self.fixtures_dir / "llm" / f"{ticket_id}.json"
        recorded = load_fixture(path).get("reply") if path.exists() else None
        if recorded is None:
            raise ReplayMissError(f"sem gravação de reply para o ticket {ticket_id}")

        result = ReplyResult.model_validate(recorded)
        if self.simulate_latency:
            await asyncio.sleep(result.latency_ms / 1000)
        return result
