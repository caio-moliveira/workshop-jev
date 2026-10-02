"""Valores esperados calculados à mão, a partir das tabelas abaixo (não pelo código)."""

import pytest

from app.config import load_config
from app.dataset import Question
from app.graph import NodeMetric, RunResult
from app.metrics.aggregator import aggregate, percentile

# pergunta: (tool do gabarito, injection)
LABELS = {
    "t1": ("vendas_mensal", False),
    "t2": ("kpis", False),
    "t3": ("top_produtos", False),
    "t4": ("vendas_mensal", False),
    "t5": ("nenhuma", True),  # bloqueada no guardrail: nunca chega à triagem
}

# provider: pergunta -> (tool escolhida, latência da triagem)
TRIAGE = {
    "jev": {
        "t1": ("vendas_mensal", 10),
        "t2": ("kpis", 20),
        "t3": ("vendas_mensal", 30),
        "t4": ("vendas_mensal", 40),
    },
    "llm": {
        "t1": ("vendas_mensal", 1000),
        "t2": ("vendas_por_vendedor", 1200),
        "t3": ("top_produtos", 1400),
        "t4": ("kpis", 1600),
    },
}


def question(id: str) -> Question:
    tool, injection = LABELS[id]
    return Question.model_validate(
        {
            "id": id,
            "text": "...",
            "labels": {"tool": tool},
            "guardrail": {"injection": injection, "dado_sensivel": False, "fora_escopo": False},
            "tags": ["bloqueada"] if injection else ["vendas"],
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
    blocked = LABELS[id][1]
    metrics = [guardrail("jev", 0.9 if blocked else 0.1), guardrail("llm", 0.4 if blocked else 0.1)]
    if not blocked:
        for provider, rows in TRIAGE.items():
            tool, latency = rows[id]
            metrics.append(metric("triage", provider, {"tool": tool}, latency=latency))
    return RunResult(
        run_id=f"run-{id}",
        config_version="2",
        mode="replay",
        question_id=id,
        question="...",
        guardrail=None,
        triage=None,
        tool_result=None,
        draft_reply=None,
        verify=None,
        action="blocked" if blocked else "human",
        reason=None,
        path=["guardrail"] if blocked else ["guardrail", "triage", "act"],
        metrics=metrics,
        errors=[],
    )


@pytest.fixture
def report():
    ids = list(LABELS)
    return aggregate("b1", [run(i) for i in ids], [question(i) for i in ids], load_config())


def test_acuracia_da_escolha_da_tool(report):
    assert report.by_question["tool"]["jev"].accuracy == pytest.approx(0.75)
    assert report.by_question["tool"]["llm"].accuracy == pytest.approx(0.5)  # acerta t1 e t3


def test_pergunta_bloqueada_fica_fora_do_denominador_da_triagem(report):
    assert report.by_question["tool"]["jev"].n == 4
    assert report.by_question["injection"]["jev"].n == 5


def test_guardrail_usa_limiar_de_meio(report):
    # Jev acerta as cinco; o LLM dá 0,4 para a bloqueada e erra essa.
    assert report.by_question["injection"]["jev"].accuracy == pytest.approx(1.0)
    assert report.by_question["injection"]["llm"].accuracy == pytest.approx(0.8)


def test_f1_macro_da_tool(report):
    # Jev: vendas_mensal P=2/3 R=1 F1=0,8; kpis F1=1; top_produtos F1=0 → (0,8 + 1 + 0) / 3
    assert report.by_question["tool"]["jev"].f1_macro == pytest.approx(0.6)
    assert report.by_question["injection"]["jev"].f1_macro is None


def test_latencia_p50_e_p95_por_node(report):
    triage = report.by_node["triage"]["jev"]

    assert triage.latency_p50 == pytest.approx(25.0)
    assert triage.latency_p95 == pytest.approx(38.5)
    assert triage.calls == 4
    assert sorted(triage.latencies) == [10, 20, 30, 40]


def test_custo_total_e_por_mil_perguntas(report):
    jev = report.by_provider["jev"]

    # 5 chamadas de guardrail + 4 de triagem, US$ 0,001 cada, em 5 perguntas
    assert jev.cost_total == pytest.approx(0.009)
    assert jev.cost_per_1000 == pytest.approx(1.8)


def test_concordancia_entre_providers(report):
    assert report.agreement["tool"] == pytest.approx(0.25)
    assert report.agreement["injection"] == pytest.approx(0.8)


def test_um_provider_so_nao_tem_concordancia():
    only_jev = run("t1")
    only_jev.metrics = [m for m in only_jev.metrics if m.provider == "jev"]

    report = aggregate("b1", [only_jev], [question("t1")], load_config())

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

    report = aggregate("b1", [broken], [question("t1")], load_config())

    assert report.by_question["tool"]["llm"].accuracy == 0
    assert report.by_node["triage"]["llm"].parse_fail_rate == 1


def test_linhas_por_pergunta_marcam_discordancia_e_erro(report):
    rows = {row.question_id: row for row in report.questions}

    assert rows["t1"].disagrees is False
    assert rows["t2"].disagrees is True
    assert rows["t1"].wrong is False
    assert rows["t3"].wrong is True  # o Jev, primário, errou a tool
    assert rows["t2"].answers["tool"] == {"jev": "kpis", "llm": "vendas_por_vendedor"}
    assert rows["t2"].labels["tool"] == "kpis"


def test_percentil_interpolado():
    assert percentile([10, 20, 30, 40], 0.5) == pytest.approx(25)
    assert percentile([10, 20, 30, 40], 0.95) == pytest.approx(38.5)
    assert percentile([7], 0.95) == 7
    assert percentile([], 0.5) is None
