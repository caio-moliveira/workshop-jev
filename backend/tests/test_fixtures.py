"""Contrato das fixtures de replay versionadas em backend/fixtures/replay/."""

import pytest

from app.dataset import load_golden_set
from app.providers.base import NodeSpec
from app.providers.replay import FIXTURES_DIR, ReplayProvider, load_fixture

FIXTURES = sorted(p for source in ("jev", "llm") for p in (FIXTURES_DIR / source).glob("*.json"))
DECISION_NODES = {"guardrail", "triage", "verify"}


def test_existem_fixtures_para_as_perguntas_do_job_de_ci():
    for source in ("jev", "llm"):
        for question_id in ("q-001", "q-022", "q-043", "adv-001"):
            assert (FIXTURES_DIR / source / f"{question_id}.json").exists()


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: f"{p.parent.name}/{p.stem}")
async def test_fixture_segue_o_contrato(path):
    source, question_id = path.parent.name, path.stem
    fixture = load_fixture(path)
    provider = ReplayProvider(source, simulate_latency=False)

    assert fixture["question_id"] == question_id
    assert set(fixture["nodes"]) <= DECISION_NODES
    assert ("reply" in fixture) == (source == "llm" and "verify" in fixture["nodes"])
    for node in fixture["nodes"]:
        result = await provider.decide(
            NodeSpec(name=node, state_fields=[], questions=[]), {"question_id": question_id}
        )
        assert result.provider == source


def test_fixtures_sao_de_perguntas_do_golden_set():
    ids = {q.id for q in load_golden_set()}

    assert {path.stem for path in FIXTURES} <= ids


def test_resposta_gravada_diz_de_qual_consulta_e():
    for path in (FIXTURES_DIR / "llm").glob("*.json"):
        fixture = load_fixture(path)
        if "reply" in fixture:
            jev = load_fixture(FIXTURES_DIR / "jev" / path.name)
            assert fixture["reply"]["tool"] == jev["nodes"]["triage"]["answers"]["tool"]["value"]
