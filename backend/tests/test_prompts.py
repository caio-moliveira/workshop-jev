"""System prompt por etapa para o LLM, com a mesma saída estruturada (SPEC-12)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import load_config
from app.graph import build_providers
from app.main import create_app
from app.prompts import load_prompt, load_prompts
from app.providers.llm import build_prompt, build_schema
from app.providers.replay import ReplayMissError, has_fixture
from app.specs import NODE_SPECS, TRIAGE
from app.tools import TOOLS

PAYLOAD = {"question_id": "q-001", "question": "Qual região vendeu mais em 2026?"}


@pytest.mark.parametrize("node", NODE_SPECS.values(), ids=lambda n: n.name)
def test_modo_native_usa_o_system_prompt_da_etapa_e_so_o_estado(node):
    system, human = build_prompt(node, PAYLOAD, "native")

    assert system.content == load_prompt(node.name)
    assert "Qual região vendeu mais em 2026?" in human.content
    assert "q-001" not in human.content  # o id só serve ao replay
    for question in node.questions:
        assert question.instructions not in system.content + human.content


def test_modo_spec_continua_igual():
    messages = build_prompt(TRIAGE, PAYLOAD)

    assert "Perguntas:" in messages[-1].content
    assert build_prompt(TRIAGE, PAYLOAD, "spec") == messages


@pytest.mark.parametrize("node", NODE_SPECS.values(), ids=lambda n: n.name)
def test_saida_estruturada_e_a_mesma_nos_dois_modos(node):
    # build_schema só recebe o NodeSpec: o modo de prompt não tem como mudar a saída.
    assert set(build_schema(node).model_fields) == {q.name for q in node.questions}


def test_roteador_lista_todas_as_tools_e_nenhuma():
    prompt = load_prompt("triage")

    assert "{tools}" not in prompt
    for tool in TOOLS.values():
        assert f"`{tool.name}`" in prompt
    assert "`nenhuma`" in prompt


def test_prompts_das_tres_etapas():
    assert set(load_prompts()) == {"guardrail", "triage", "verify"}


async def test_replay_native_sem_gravacao_nao_reaproveita_o_modo_spec():
    config = load_config().model_copy(update={"mode": "replay", "llm_prompt_style": "native"})
    providers = build_providers(config, simulate_latency=False)

    assert not has_fixture("q-001", prompt_style="native")
    with pytest.raises(ReplayMissError, match="llm-native"):
        await providers.llm.decide(TRIAGE, PAYLOAD)


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "replay")
    app = create_app(runs_dir=tmp_path / "runs", simulate_latency=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_get_prompts(client):
    prompts = (await client.get("/prompts")).json()

    assert prompts["triage"] == load_prompt("triage")


async def test_trocar_para_native_na_configuracao(client):
    config = (await client.get("/config")).json()
    assert config["llm_prompt_style"] == "spec"

    config["llm_prompt_style"] = "native"
    assert (await client.put("/config", json=config)).status_code == 200
    dataset = (await client.get("/dataset")).json()

    # Em replay, sem gravação no modo native, nenhuma pergunta fica disponível.
    assert not any(q["replayable"] for q in dataset)
    response = await client.post("/runs", json={"question_id": "q-001"})
    assert response.status_code == 422

    config["llm_prompt_style"] = "rascunho"
    assert (await client.put("/config", json=config)).status_code == 422
