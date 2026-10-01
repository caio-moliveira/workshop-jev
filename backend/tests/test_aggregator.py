"""Valores esperados calculados à mão, a partir das tabelas abaixo (não pelo código)."""

import pytest

from app.config import load_config
from app.dataset import Ticket
from app.graph import NodeMetric, RunResult
from app.metrics.aggregator import aggregate, percentile

# ticket: (fila, urgencia, pede_reembolso, injection)
LABELS = {
    "t1": ("financeiro", 2, True, False),
    "t2": ("pedidos", 1, False, False),
    "t3": ("conta", 0, False, False),
    "t4": ("financeiro", 2, True, False),
    "t5": ("outro", 0, False, True),  # bloqueado no guardrail: nunca chega à triagem
}

# provider: ticket -> (fila, urgencia, pede_reembolso, latência da triagem)
TRIAGE = {
    "jev": {
        "t1": ("financeiro", 2, 0.9, 10),
        "t2": ("pedidos", 1, 0.2, 20),
        "t3": ("financeiro", 1, 0.6, 30),
        "t4": ("financeiro", 0, 0.4, 40),
    },
    "llm": {
        "t1": ("financeiro", 2, 0.8, 1000),
        "t2": ("conta", 1, 0.1, 1200),
        "t3": ("conta", 0, 0.7, 1400),
        "t4": ("pedidos", 2, 0.6, 1600),
    },
}


def ticket(id: str) -> Ticket:
    fila, urgencia, reembolso, injection = LABELS[id]
    return Ticket.model_validate(
        {
            "id": id,
            "text": "...",
            "channel": "chat",
            "labels": {
                "fila": fila,
                "urgencia": urgencia,
                "pede_reembolso": reembolso,
                "risco_churn": False,
            },
            "guardrail": {"injection": injection, "dado_sensivel": False, "fora_escopo": False},
            "tags": ["bloqueado"] if injection else ["triagem"],
            "difficulty": "easy",
        }
    )


def metric(node, provider, answers, latency=10.0, cost=0.001, **flags) -> NodeMetric:
    return NodeMetric(
        provider=provider,
        model=f"{provider}-model",
        answers={k: {"value": v, "confidence": 0.9} for k, v in answers.items()},
        latency_ms=latency,
        tokens_in=100,
        tokens_out=5,
        cost_usd=cost,
        parse_ok=flags.get("parse_ok", True),
        values_in_schema=flags.get("values_in_schema", True),
        raw={},
        node=node,
        is_primary=provider == "jev",
    )


def guardrail(provider: str, injection: float) -> NodeMetric:
    return metric(
        "guardrail",
        provider,
        {"injection": injection, "dado_sensivel": 0.01, "fora_escopo": 0.02},
    )


def run(id: str) -> RunResult:
    blocked = LABELS[id][3]
    metrics = [guardrail("jev", 0.9 if blocked else 0.1), guardrail("llm", 0.4 if blocked else 0.1)]
    if not blocked:
        for provider, rows in TRIAGE.items():
            fila, urgencia, reembolso, latency = rows[id]
            answers = {
                "fila": fila,
                "urgencia": urgencia,
                "pede_reembolso": reembolso,
                "risco_churn": 0.1,
            }
            metrics.append(metric("triage", provider, answers, latency=latency))
    return RunResult(
        run_id=f"run-{id}",
        config_version="1",
        mode="replay",
        ticket_id=id,
        guardrail=None,
        triage=None,
        draft_reply=None,
        verify=None,
        action="blocked" if blocked else "human",
        path=["guardrail"] if blocked else ["guardrail", "triage", "act"],
        metrics=metrics,
        errors=[],
    )


@pytest.fixture
def report():
    ids = list(LABELS)
    return aggregate("b1", [run(i) for i in ids], [ticket(i) for i in ids], load_config())


def test_acuracia_por_pergunta_e_provider(report):
    assert report.by_question["fila"]["jev"].accuracy == pytest.approx(0.75)
    assert report.by_question["fila"]["llm"].accuracy == pytest.approx(0.5)  # acerta t1 e t3
    assert report.by_question["urgencia"]["jev"].accuracy == pytest.approx(0.5)
    assert report.by_question["pede_reembolso"]["jev"].accuracy == pytest.approx(0.5)
    assert report.by_question["pede_reembolso"]["llm"].accuracy == pytest.approx(0.75)


def test_ticket_bloqueado_fica_fora_do_denominador_da_triagem(report):
    assert report.by_question["fila"]["jev"].n == 4
    assert report.by_question["injection"]["jev"].n == 5


def test_guardrail_usa_limiar_de_meio(report):
    # Jev acerta os cinco; o LLM dá 0,4 para o bloqueado e erra esse.
    assert report.by_question["injection"]["jev"].accuracy == pytest.approx(1.0)
    assert report.by_question["injection"]["llm"].accuracy == pytest.approx(0.8)


def test_f1_macro_da_fila(report):
    # Jev: financeiro P=2/3 R=1 F1=0,8; pedidos F1=1; conta F1=0 → (0,8 + 1 + 0) / 3
    assert report.by_question["fila"]["jev"].f1_macro == pytest.approx(0.6)


def test_erro_absoluto_medio_da_urgencia(report):
    # Jev: |2-2| + |1-1| + |1-0| + |0-2| = 3 → 3/4
    assert report.by_question["urgencia"]["jev"].mae == pytest.approx(0.75)
    assert report.by_question["fila"]["jev"].mae is None


def test_latencia_p50_e_p95_por_node(report):
    triage = report.by_node["triage"]["jev"]

    assert triage.latency_p50 == pytest.approx(25.0)
    assert triage.latency_p95 == pytest.approx(38.5)
    assert triage.calls == 4
    assert sorted(triage.latencies) == [10, 20, 30, 40]


def test_custo_total_e_por_mil_tickets(report):
    jev = report.by_provider["jev"]

    # 5 chamadas de guardrail + 4 de triagem, US$ 0,001 cada, em 5 tickets
    assert jev.cost_total == pytest.approx(0.009)
    assert jev.cost_per_1000 == pytest.approx(1.8)


def test_concordancia_entre_providers(report):
    assert report.agreement["fila"] == pytest.approx(0.25)
    assert report.agreement["pede_reembolso"] == pytest.approx(0.75)
    assert report.agreement["injection"] == pytest.approx(0.8)


def test_um_provider_so_nao_tem_concordancia():
    only_jev = run("t1")
    only_jev.metrics = [m for m in only_jev.metrics if m.provider == "jev"]

    report = aggregate("b1", [only_jev], [ticket("t1")], load_config())

    assert report.agreement == {}
    assert "llm" not in report.by_provider


def test_falha_de_parsing_conta_como_erro_e_entra_na_taxa():
    broken = run("t1")
    broken.metrics = [
        m
        if m.node != "triage" or m.provider != "llm"
        else metric("triage", "llm", {}, parse_ok=False)
        for m in broken.metrics
    ]

    report = aggregate("b1", [broken], [ticket("t1")], load_config())

    assert report.by_question["fila"]["llm"].accuracy == 0
    assert report.by_node["triage"]["llm"].parse_fail_rate == 1


def test_linhas_por_ticket_marcam_discordancia_e_erro(report):
    rows = {row.ticket_id: row for row in report.tickets}

    assert rows["t1"].disagrees is False
    assert rows["t2"].disagrees is True
    assert rows["t1"].wrong is False
    assert rows["t3"].wrong is True  # o Jev, primário, errou a fila
    assert rows["t2"].answers["fila"] == {"jev": "pedidos", "llm": "conta"}
    assert rows["t2"].labels["fila"] == "pedidos"


def test_percentil_interpolado():
    assert percentile([10, 20, 30, 40], 0.5) == pytest.approx(25)
    assert percentile([10, 20, 30, 40], 0.95) == pytest.approx(38.5)
    assert percentile([7], 0.95) == 7
    assert percentile([], 0.5) is None
