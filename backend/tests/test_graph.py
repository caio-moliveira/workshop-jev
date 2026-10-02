import asyncio

import pytest

from app.config import GraphConfig, load_config
from app.dataset import Question, load_golden_set
from app.graph import Event, Providers, ReplyResult, run_question
from app.providers.base import Answer, NodeSpec, ProviderResult
from app.tools import ToolResult

QUESTION = Question.model_validate(
    {
        "id": "q-0042",
        "text": "Qual região vendeu mais este ano?",
        "labels": {"tool": "vendas_por_regiao"},
        "guardrail": {"injection": False, "dado_sensivel": False, "fora_escopo": False},
        "tags": [],
        "difficulty": "easy",
    }
)


def noul(p: float) -> Answer:
    return Answer(value=p)


def tool(value: str, confidence: float) -> dict:
    return {"tool": Answer(value=value, confidence=confidence)}


SAFE = {"injection": noul(0.01), "dado_sensivel": noul(0.02), "fora_escopo": noul(0.03)}
TRIAGE_OK = tool("vendas_por_regiao", 0.92)
VERIFY_OK = {
    "fiel_aos_dados": noul(0.95),
    "responde_pergunta": noul(0.9),
    "inventa_numero": noul(0.05),
}


def result(provider: str, answers: dict, **fields) -> ProviderResult:
    return ProviderResult(
        provider=provider,
        model=f"{provider}-model",
        answers=answers,
        latency_ms=10,
        tokens_in=100,
        tokens_out=5,
        cost_usd=0.001,
        parse_ok=fields.get("parse_ok", True),
        values_in_schema=fields.get("values_in_schema", True),
        raw={},
    )


class FakeProvider:
    def __init__(self, name: str, **answers):
        self.name = name
        self.answers = {"guardrail": SAFE, "triage": TRIAGE_OK, "verify": VERIFY_OK} | answers
        self.calls: list[tuple[str, dict]] = []

    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult:
        self.calls.append((node.name, payload))
        answers = self.answers[node.name]
        if isinstance(answers, Exception):
            raise answers
        if isinstance(answers, ProviderResult):
            return answers
        return result(self.name, answers)


class FakeReply:
    def __init__(self):
        self.payloads: list[dict] = []

    @property
    def calls(self) -> int:
        return len(self.payloads)

    async def write(self, payload: dict) -> ReplyResult:
        self.payloads.append(payload)
        return ReplyResult(
            text="O Sudeste vendeu mais: R$ 100,00.",
            model="llm-model",
            latency_ms=20,
            tokens_in=300,
            tokens_out=40,
            cost_usd=0.002,
        )


class FakeTools:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[str] = []

    async def run(self, name: str) -> ToolResult:
        self.calls.append(name)
        if self.error:
            raise self.error
        return ToolResult(
            tool=name,
            view=f"vw_{name}",
            columns=["regiao", "receita"],
            rows=[{"regiao": "Sudeste", "receita": 100.0}, {"regiao": "Sul", "receita": 50.0}],
            row_count=2,
            truncated=False,
            latency_ms=3,
        )


def config(**changes) -> GraphConfig:
    return load_config().model_copy(update={"mode": "replay"} | changes)


def providers(jev=None, llm=None, tools=None) -> Providers:
    return Providers(
        jev=jev or FakeProvider("jev"),
        llm=llm or FakeProvider("llm"),
        reply=FakeReply(),
        tools=tools or FakeTools(),
    )


async def run(cfg=None, prov=None, emit=None):
    return await run_question(QUESTION, cfg or config(), emit=emit, providers=prov or providers())


async def test_caminho_feliz_libera_a_resposta():
    prov = providers()

    outcome = await run(prov=prov)

    assert outcome.path == ["guardrail", "triage", "tool", "reply", "verify", "act"]
    assert outcome.action == "auto"
    assert outcome.reason is None
    assert outcome.draft_reply == "O Sudeste vendeu mais: R$ 100,00."
    assert outcome.tool_result.tool == "vendas_por_regiao"
    assert prov.tools.calls == ["vendas_por_regiao"]
    assert outcome.errors == []
    assert outcome.config_version == "2"


async def test_injection_acima_do_limiar_bloqueia_no_guardrail():
    prov = providers(jev=FakeProvider("jev", guardrail=SAFE | {"injection": noul(0.75)}))

    outcome = await run(prov=prov)

    assert outcome.action == "blocked"
    assert outcome.path == ["guardrail"]
    assert "manipular" in outcome.reason
    assert outcome.triage is None and outcome.tool_result is None
    assert prov.tools.calls == [] and prov.reply.calls == 0


async def test_nenhuma_tool_vai_para_humano_sem_consultar():
    prov = providers(jev=FakeProvider("jev", triage=tool("nenhuma", 0.95)))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert outcome.path == ["guardrail", "triage", "act"]
    assert "nenhuma consulta" in outcome.reason
    assert prov.tools.calls == []


async def test_confianca_baixa_na_tool_vai_para_humano():
    prov = providers(jev=FakeProvider("jev", triage=tool("kpis", 0.6)))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert outcome.path == ["guardrail", "triage", "act"]
    assert "60%" in outcome.reason


async def test_tool_que_falha_vai_para_humano_sem_reply():
    prov = providers(tools=FakeTools(error=ConnectionRefusedError("banco fora do ar")))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert outcome.path == ["guardrail", "triage", "tool", "act"]
    assert any("banco fora do ar" in e for e in outcome.errors)
    assert outcome.reason == "a consulta aos dados falhou"
    assert prov.reply.calls == 0


async def test_numero_inventado_vai_para_humano():
    prov = providers(jev=FakeProvider("jev", verify=VERIFY_OK | {"inventa_numero": noul(0.4)}))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert outcome.path == ["guardrail", "triage", "tool", "reply", "verify", "act"]
    assert "número" in outcome.reason


async def test_resposta_infiel_aos_dados_vai_para_humano():
    prov = providers(jev=FakeProvider("jev", verify=VERIFY_OK | {"fiel_aos_dados": noul(0.5)}))

    assert (await run(prov=prov)).action == "human"


async def test_em_both_roda_a_tool_do_primario_e_os_dois_ficam_nas_metricas():
    prov = providers(llm=FakeProvider("llm", triage=tool("kpis", 0.9)))

    outcome = await run(prov=prov)

    assert prov.tools.calls == ["vendas_por_regiao"]
    assert outcome.triage["tool"]["value"] == "vendas_por_regiao"
    triage_metrics = [m for m in outcome.metrics if m.node == "triage"]
    assert {(m.provider, m.is_primary) for m in triage_metrics} == {("jev", True), ("llm", False)}


async def test_trocar_o_primario_muda_a_tool():
    prov = providers(llm=FakeProvider("llm", triage=tool("kpis", 0.9)))

    await run(cfg=config(primary="llm"), prov=prov)

    assert prov.tools.calls == ["kpis"]


async def test_mudar_o_limiar_muda_a_decisao():
    prov = providers(jev=FakeProvider("jev", triage=tool("vendas_por_regiao", 0.85)))
    cfg = config()
    stricter = cfg.thresholds.model_copy(update={"triage_min_confidence": 0.9})

    assert (await run(cfg=cfg, prov=prov)).action == "auto"
    assert (await run(cfg=config(thresholds=stricter), prov=prov)).action == "human"


async def test_node_com_um_so_provider_roda_so_ele():
    cfg = config(providers={"guardrail": "jev", "triage": "llm", "verify": "both"})
    prov = providers()

    outcome = await run(cfg=cfg, prov=prov)

    assert [n for n, _ in prov.jev.calls] == ["guardrail", "verify"]
    assert [n for n, _ in prov.llm.calls] == ["triage", "verify"]
    triage = [m for m in outcome.metrics if m.node == "triage"]
    assert [(m.provider, m.is_primary) for m in triage] == [("llm", True)]


async def test_primario_com_falha_de_parsing_vai_para_humano():
    prov = providers(jev=FakeProvider("jev", triage=result("jev", {}, parse_ok=False)))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert outcome.errors


async def test_primario_com_tool_inventada_vai_para_humano():
    invented = result("jev", tool("vw_secreta", 0.99), values_in_schema=False)
    prov = providers(jev=FakeProvider("jev", triage=invented))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert prov.tools.calls == []
    assert outcome.errors


async def test_excecao_no_primario_vai_para_humano():
    prov = providers(jev=FakeProvider("jev", guardrail=RuntimeError("timeout")))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert any("timeout" in e for e in outcome.errors)


async def test_falha_no_secundario_so_e_registrada():
    prov = providers(llm=FakeProvider("llm", triage=RuntimeError("rate limit")))

    outcome = await run(prov=prov)

    assert outcome.action == "auto"
    assert any("rate limit" in e for e in outcome.errors)


async def test_payload_nao_vaza_os_rotulos_do_golden_set():
    prov = providers()

    await run(prov=prov)

    for _, payload in prov.jev.calls:
        assert "labels" not in str(payload)
        assert payload["question"] == QUESTION.text
        assert payload["question_id"] == QUESTION.id
    verify_payload = dict(prov.jev.calls)["verify"]
    assert verify_payload["draft_reply"] == "O Sudeste vendeu mais: R$ 100,00."
    assert verify_payload["tool_result"]["rows"][0] == {"regiao": "Sudeste", "receita": 100.0}
    assert "latency_ms" not in verify_payload["tool_result"]
    (reply_payload,) = prov.reply.payloads
    assert "labels" not in str(reply_payload)
    assert reply_payload["tool"]["name"] == "vendas_por_regiao"
    assert reply_payload["data"]["columns"] == ["regiao", "receita"]


async def test_payload_e_o_mesmo_para_os_dois_providers():
    prov = providers()

    await run(prov=prov)

    assert prov.jev.calls == prov.llm.calls


async def test_eventos_saem_na_ordem():
    events: list[Event] = []

    async def emit(event: Event):
        events.append(event)

    outcome = await run(emit=emit)

    kinds = [(e.type, e.node) for e in events]
    assert kinds[0] == ("run.started", None)
    assert kinds[-1] == ("run.finished", None)
    assert kinds[1:5] == [
        ("node.started", "guardrail"),
        ("provider.finished", "guardrail"),
        ("provider.finished", "guardrail"),
        ("node.finished", "guardrail"),
    ]
    tool_index = kinds.index(("node.started", "tool"))
    assert kinds[tool_index : tool_index + 3] == [
        ("node.started", "tool"),
        ("tool.finished", "tool"),
        ("node.finished", "tool"),
    ]
    started = [n for t, n in kinds if t == "node.started"]
    assert started == outcome.path
    assert all(e.run_id == outcome.run_id for e in events)
    assert events[0].data["question"] == QUESTION.text
    assert events[-1].data["action"] == "auto"


@pytest.mark.parametrize(
    "question_id,action,path",
    [
        ("q-001", "auto", ["guardrail", "triage", "tool", "reply", "verify", "act"]),
        ("q-022", "auto", ["guardrail", "triage", "tool", "reply", "verify", "act"]),
        ("q-043", "auto", ["guardrail", "triage", "tool", "reply", "verify", "act"]),
        ("q-045", "auto", ["guardrail", "triage", "tool", "reply", "verify", "act"]),
        ("q-050", "human", ["guardrail", "triage", "act"]),
        ("adv-001", "blocked", ["guardrail"]),
    ],
)
async def test_replay_das_fixtures_versionadas(question_id, action, path):
    question = next(q for q in load_golden_set() if q.id == question_id)

    outcome = await run_question(question, config(), simulate_latency=False)

    assert outcome.mode == "replay"
    assert (outcome.action, outcome.path) == (action, path)
    assert outcome.errors == []


class SlowProvider(FakeProvider):
    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult:
        await asyncio.sleep(0.05)
        return await super().decide(node, payload)


async def test_cada_provider_e_emitido_quando_termina():
    events: list[Event] = []

    async def emit(event: Event):
        events.append(event)

    await run(prov=providers(jev=SlowProvider("jev")), emit=emit)

    guardrail = [
        e.data["provider"]
        for e in events
        if e.type == "provider.finished" and e.node == "guardrail"
    ]
    assert guardrail == ["llm", "jev"]
