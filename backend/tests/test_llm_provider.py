import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from app.metrics.pricing import Pricing
from app.providers.llm import LLMProvider, build_prompt
from app.specs import NODE_SPECS

from .mixed_spec import TRIAGE

PRICING = Pricing.model_validate(
    {
        "reference_date": "x",
        "source": "x",
        "models": {"gpt-5.6-luna": {"input": 0.2, "output": 1.2}},
    }
)

VALID = {
    "fila": {"value": "financeiro", "confidence": 0.9},
    "urgencia": {"value": 2, "confidence": 0.8},
    "pede_reembolso": {"value": 0.95, "confidence": 0.9},
    "risco_churn": {"value": 0.1, "confidence": 0.85},
}


class FakeChatModel:
    """Chat model que devolve um JSON fixo e o valida contra o schema pedido,
    como `with_structured_output(..., include_raw=True)` faz."""

    def __init__(self, data: dict, usage=(1200, 90)):
        self.data = data
        self.usage = usage
        self.messages = None

    def with_structured_output(self, schema, include_raw=False):
        assert include_raw
        model = self

        class Runnable:
            async def ainvoke(self, messages):
                model.messages = messages
                raw = AIMessage(
                    content=str(model.data),
                    usage_metadata={
                        "input_tokens": model.usage[0],
                        "output_tokens": model.usage[1],
                        "total_tokens": sum(model.usage),
                    },
                )
                try:
                    return {
                        "raw": raw,
                        "parsed": schema.model_validate(model.data),
                        "parsing_error": None,
                    }
                except ValidationError as error:
                    return {"raw": raw, "parsed": None, "parsing_error": error}

        return Runnable()


def provider(data: dict) -> LLMProvider:
    return LLMProvider("openai:gpt-5.6-luna", PRICING, chat_model=FakeChatModel(data))


async def test_resposta_valida():
    result = await provider(VALID).decide(TRIAGE, {"ticket": {"text": "..."}})

    assert result.provider == "llm"
    assert result.model == "gpt-5.6-luna"
    assert result.parse_ok and result.values_in_schema
    assert (result.answers["fila"].value, result.answers["fila"].confidence) == ("financeiro", 0.9)
    assert result.answers["urgencia"].value == 2
    assert result.answers["fila"].probabilities is None
    assert (result.tokens_in, result.tokens_out) == (1200, 90)
    assert result.cost_usd == pytest.approx((1200 * 0.2 + 90 * 1.2) / 1_000_000)


async def test_json_invalido_registra_falha_sem_excecao():
    result = await provider({"fila": "financeiro"}).decide(TRIAGE, {"ticket": {"text": "..."}})

    assert not result.parse_ok
    assert result.answers == {}
    assert result.tokens_in == 1200


async def test_fila_inventada_fica_fora_do_schema():
    data = VALID | {"fila": {"value": "suporte", "confidence": 0.9}}

    result = await provider(data).decide(TRIAGE, {"ticket": {"text": "..."}})

    assert result.parse_ok
    assert not result.values_in_schema


@pytest.mark.parametrize(
    "question,value",
    [("urgencia", 3), ("pede_reembolso", 1.4), ("risco_churn", -0.1)],
)
async def test_score_ou_noul_fora_da_escala_fica_fora_do_schema(question, value):
    data = VALID | {question: {"value": value, "confidence": 0.9}}

    result = await provider(data).decide(TRIAGE, {"ticket": {"text": "..."}})

    assert not result.values_in_schema


@pytest.mark.parametrize("node", NODE_SPECS.values(), ids=lambda n: n.name)
def test_prompt_vem_do_mesmo_spec_que_o_jev(node):
    payload = {"ticket": {"text": "Fui cobrado duas vezes"}}

    prompt = "\n".join(str(m.content) for m in build_prompt(node, payload))

    assert "Fui cobrado duas vezes" in prompt
    for question in node.questions:
        assert question.name in prompt
        assert question.instructions in prompt
        criteria = question.criteria
        descriptions = criteria.values() if isinstance(criteria, dict) else criteria
        for description in descriptions:
            assert description in prompt
        if question.type == "choice":
            for option in criteria:
                assert option in prompt
