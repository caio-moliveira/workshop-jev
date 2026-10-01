"""Chama o Jev (TypeSafe system_one) a partir de um NodeSpec."""

import time

from typesafe_sdk import AsyncTypeSafeClient, ChoiceAnswer, ScoreAnswer

from app.metrics.pricing import Pricing, cost_usd
from app.providers.base import Answer, NodeSpec, ProviderResult


class JevProvider:
    def __init__(
        self,
        pricing: Pricing,
        model: str = "jev-1.13.0",
        client: AsyncTypeSafeClient | None = None,
    ):
        self.pricing = pricing
        self.model = model
        self.client = client or AsyncTypeSafeClient()

    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult:
        questions = {
            q.name: {"type": q.type, "instructions": q.instructions, "criteria": q.criteria}
            for q in node.questions
        }

        start = time.perf_counter()
        response = await self.client.system_one(
            state=payload, questions=questions, model=self.model
        )
        latency_ms = (time.perf_counter() - start) * 1000

        tokens_in = response.usage.input_tokens or 0
        tokens_out = response.usage.output_tokens or 0
        return ProviderResult(
            provider="jev",
            model=response.model,
            answers={name: to_answer(answer) for name, answer in response.answers.items()},
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd(response.model, tokens_in, tokens_out, self.pricing),
            parse_ok=True,
            values_in_schema=True,
            raw=response.model_dump(mode="json"),
        )


def to_answer(answer) -> Answer:
    if isinstance(answer, ChoiceAnswer):
        return Answer(
            value=answer.choice,
            confidence=answer.confidence,
            probabilities=dict(answer.probabilities),
        )
    if isinstance(answer, ScoreAnswer):
        level = max(answer.probabilities, key=answer.probabilities.get)
        return Answer(
            value=level,
            confidence=answer.confidence,
            probabilities={str(k): p for k, p in answer.probabilities.items()},
        )
    return Answer(value=answer.noul)
