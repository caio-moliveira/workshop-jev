"""Chama um LLM com structured output a partir do mesmo NodeSpec do Jev (PRD 7.2)."""

import json
import time

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field, create_model

from app.config import PromptStyle
from app.metrics.pricing import Pricing, cost_usd
from app.prompts import load_prompt
from app.providers.base import Answer, DecisionSpec, NodeSpec, ProviderResult

SYSTEM_PROMPT = (
    "Você toma decisões sobre o estado recebido. Responda cada pergunta só com base nele, "
    "usando exatamente os valores permitidos, e informe sua confiança de 0 a 1 "
    "em cada resposta."
)

# `choice` fica como str livre no schema de saída, de propósito: é o que permite medir
# quando o LLM inventa uma opção (values_in_schema).
VALUE_TYPES = {"choice": str, "score": int, "noul": float}


class LLMProvider:
    def __init__(
        self,
        model: str,
        pricing: Pricing,
        chat_model: BaseChatModel | None = None,
        prompt_style: PromptStyle = "spec",
    ):
        self.model = model
        self.model_id = model.split(":", 1)[-1]
        self.pricing = pricing
        self.prompt_style = prompt_style
        self.chat_model = chat_model or init_chat_model(model, **decision_kwargs(model))

    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult:
        structured = self.chat_model.with_structured_output(build_schema(node), include_raw=True)

        start = time.perf_counter()
        output = await structured.ainvoke(build_prompt(node, payload, self.prompt_style))
        latency_ms = (time.perf_counter() - start) * 1000

        raw = output["raw"]
        usage = raw.usage_metadata or {}
        tokens_in, tokens_out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        parsed = output["parsed"]
        answers = (
            {name: Answer(**field) for name, field in parsed.model_dump().items()} if parsed else {}
        )
        return ProviderResult(
            provider="llm",
            model=self.model_id,
            answers=answers,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd(self.model_id, tokens_in, tokens_out, self.pricing),
            parse_ok=parsed is not None,
            values_in_schema=parsed is not None and in_schema(node, answers),
            raw={
                "content": raw.content,
                "parsing_error": str(output["parsing_error"]) if output["parsing_error"] else None,
                "prompt_style": self.prompt_style,
            },
        )


def decision_kwargs(model: str) -> dict:
    """Decisão simples: sem raciocínio estendido (PRD 7.7)."""
    return {"reasoning_effort": "none"} if model.startswith("openai:") else {}


def build_schema(node: NodeSpec) -> type[BaseModel]:
    fields = {}
    for q in node.questions:
        answer = create_model(
            f"{node.name}_{q.name}",
            value=(VALUE_TYPES[q.type], Field(description=describe_value(q))),
            confidence=(float, Field(description="Sua confiança na resposta, de 0 a 1.")),
        )
        fields[q.name] = (answer, Field(description=q.instructions))
    return create_model(f"{node.name}_answers", **fields)


def build_prompt(node: NodeSpec, payload: dict, style: PromptStyle = "spec") -> list[BaseMessage]:
    if style == "native":
        # Como em produção: o system prompt da etapa e, na mensagem, só o que o usuário e o
        # sistema produziram. O schema de saída continua o mesmo do modo spec.
        state = {k: v for k, v in payload.items() if k != "question_id"}
        content = json.dumps(state, ensure_ascii=False, indent=2, default=str)
        return [SystemMessage(load_prompt(node.name)), HumanMessage(content)]
    questions = "\n\n".join(describe_question(q) for q in node.questions)
    state = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    return [
        SystemMessage(SYSTEM_PROMPT),
        HumanMessage(f"Estado:\n{state}\n\nPerguntas:\n\n{questions}"),
    ]


def describe_question(q: DecisionSpec) -> str:
    return f"{q.name} ({q.type}): {q.instructions}\n{describe_value(q)}"


def describe_value(q: DecisionSpec) -> str:
    if q.type == "choice":
        options = "\n".join(f"- {label}: {text}" for label, text in q.criteria.items())
        return f"Responda com uma das opções:\n{options}"
    if q.type == "score":
        levels = "\n".join(f"- {i}: {text}" for i, text in enumerate(q.criteria))
        return f"Responda com o número do nível:\n{levels}"
    criteria = q.criteria or {}
    return (
        "Responda com a probabilidade, de 0 a 1, de a afirmação ser verdadeira.\n"
        f"- verdadeiro: {criteria.get('true', '')}\n- falso: {criteria.get('false', '')}"
    )


def in_schema(node: NodeSpec, answers: dict[str, Answer]) -> bool:
    for q in node.questions:
        value = answers[q.name].value
        if q.type == "choice" and value not in q.criteria:
            return False
        if q.type == "score" and value not in range(len(q.criteria)):
            return False
        if q.type == "noul" and not 0 <= value <= 1:
            return False
    return True
