import pytest

from app.config import GraphConfig, load_config
from app.dataset import Ticket
from app.graph import Event, Providers, ReplyResult, run_ticket
from app.providers.base import Answer, NodeSpec, ProviderResult

TICKET = Ticket.model_validate(
    {
        "id": "tk-0042",
        "text": "Fui cobrado duas vezes no pedido A-104. Quero o estorno.",
        "channel": "email",
        "labels": {
            "fila": "financeiro",
            "urgencia": 2,
            "pede_reembolso": True,
            "risco_churn": False,
        },
        "guardrail": {"injection": False, "dado_sensivel": False, "fora_escopo": False},
        "tags": [],
        "difficulty": "easy",
    }
)


def noul(p: float) -> Answer:
    return Answer(value=p)


def fila(value: str, confidence: float) -> Answer:
    return Answer(value=value, confidence=confidence)


SAFE = {"injection": noul(0.01), "dado_sensivel": noul(0.02), "fora_escopo": noul(0.03)}
TRIAGE_OK = {
    "fila": fila("financeiro", 0.92),
    "urgencia": Answer(value=2, confidence=0.8),
    "pede_reembolso": noul(0.95),
    "risco_churn": noul(0.1),
}
VERIFY_OK = {"segue_politica": noul(0.9), "responde_pedido": noul(0.9), "promete_fora": noul(0.05)}


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
            text="Seu estorno foi solicitado.",
            model="llm-model",
            latency_ms=20,
            tokens_in=300,
            tokens_out=40,
            cost_usd=0.002,
        )


def config(**changes) -> GraphConfig:
    return load_config().model_copy(update={"mode": "replay"} | changes)


def providers(jev=None, llm=None) -> Providers:
    return Providers(
        jev=jev or FakeProvider("jev"), llm=llm or FakeProvider("llm"), reply=FakeReply()
    )


async def run(cfg=None, prov=None, emit=None):
    return await run_ticket(TICKET, cfg or config(), emit=emit, providers=prov or providers())


async def test_caminho_feliz_termina_em_acao_automatica():
    outcome = await run()

    assert outcome.path == ["guardrail", "triage", "reply", "verify", "act"]
    assert outcome.action == "auto"
    assert outcome.draft_reply == "Seu estorno foi solicitado."
    assert outcome.errors == []
    assert outcome.config_version == "1"


async def test_injection_acima_do_limiar_bloqueia_no_guardrail():
    prov = providers(jev=FakeProvider("jev", guardrail=SAFE | {"injection": noul(0.75)}))

    outcome = await run(prov=prov)

    assert outcome.action == "blocked"
    assert outcome.path == ["guardrail"]
    assert outcome.triage is None and outcome.draft_reply is None
    assert prov.reply.calls == 0


async def test_fila_com_confianca_baixa_vai_para_humano_sem_reply():
    prov = providers(jev=FakeProvider("jev", triage=TRIAGE_OK | {"fila": fila("pedidos", 0.6)}))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert outcome.path == ["guardrail", "triage", "act"]
    assert prov.reply.calls == 0


async def test_promessa_fora_da_politica_vai_para_humano():
    prov = providers(jev=FakeProvider("jev", verify=VERIFY_OK | {"promete_fora": noul(0.4)}))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert outcome.path == ["guardrail", "triage", "reply", "verify", "act"]


async def test_resposta_fora_da_politica_vai_para_humano():
    prov = providers(jev=FakeProvider("jev", verify=VERIFY_OK | {"segue_politica": noul(0.5)}))

    assert (await run(prov=prov)).action == "human"


async def test_em_both_o_caminho_segue_o_primario_e_os_dois_ficam_nas_metricas():
    # O LLM manda para humano (confiança baixa); o Jev, primário, segue em frente.
    prov = providers(llm=FakeProvider("llm", triage=TRIAGE_OK | {"fila": fila("pedidos", 0.5)}))

    outcome = await run(prov=prov)

    assert outcome.action == "auto"
    assert outcome.triage["fila"]["value"] == "financeiro"
    triage_metrics = [m for m in outcome.metrics if m.node == "triage"]
    assert {(m.provider, m.is_primary) for m in triage_metrics} == {("jev", True), ("llm", False)}


async def test_trocar_o_primario_muda_o_caminho():
    prov = providers(llm=FakeProvider("llm", triage=TRIAGE_OK | {"fila": fila("pedidos", 0.5)}))

    outcome = await run(cfg=config(primary="llm"), prov=prov)

    assert outcome.action == "human"
    assert outcome.triage["fila"]["value"] == "pedidos"


async def test_mudar_o_limiar_muda_a_decisao():
    prov = providers(jev=FakeProvider("jev", triage=TRIAGE_OK | {"fila": fila("financeiro", 0.85)}))
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
    broken = result("jev", {}, parse_ok=False)
    prov = providers(jev=FakeProvider("jev", triage=broken))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
    assert outcome.errors


async def test_primario_com_valor_fora_do_schema_vai_para_humano():
    invented = result("jev", TRIAGE_OK | {"fila": fila("suporte", 0.99)}, values_in_schema=False)
    prov = providers(jev=FakeProvider("jev", triage=invented))

    outcome = await run(prov=prov)

    assert outcome.action == "human"
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
        assert payload["ticket"]["text"] == TICKET.text
    verify_payload = dict(prov.jev.calls)["verify"]
    assert verify_payload["draft_reply"] == "Seu estorno foi solicitado."
    assert "policy" in verify_payload
    (reply_payload,) = prov.reply.payloads
    assert "labels" not in str(reply_payload)
    assert reply_payload["triage"]["fila"]["value"] == "financeiro"
    assert reply_payload["policy"]


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
    started = [n for t, n in kinds if t == "node.started"]
    assert started == outcome.path
    assert all(e.run_id == outcome.run_id for e in events)
    assert events[-1].data["action"] == "auto"


@pytest.mark.parametrize(
    "ticket_id,action,path",
    [
        ("tk-0001", "auto", ["guardrail", "triage", "reply", "verify", "act"]),
        ("tk-0002", "auto", ["guardrail", "triage", "reply", "verify", "act"]),
        ("adv-001", "blocked", ["guardrail"]),
    ],
)
async def test_replay_das_fixtures_versionadas(ticket_id, action, path):
    from app.dataset import load_golden_set

    ticket = next(t for t in load_golden_set() if t.id == ticket_id)

    outcome = await run_ticket(ticket, config(), simulate_latency=False)

    assert outcome.mode == "replay"
    assert (outcome.action, outcome.path) == (action, path)
    assert outcome.errors == []
