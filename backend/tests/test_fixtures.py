"""Contrato das fixtures de replay versionadas em backend/fixtures/replay/."""

import pytest

from app.dataset import load_golden_set
from app.providers.base import NodeSpec
from app.providers.replay import FIXTURES_DIR, ReplayProvider, load_fixture

FIXTURES = sorted(p for source in ("jev", "llm") for p in (FIXTURES_DIR / source).glob("*.json"))
DECISION_NODES = {"guardrail", "triage", "verify"}


def test_existem_fixtures_para_os_tickets_do_job_de_ci():
    for source in ("jev", "llm"):
        for ticket_id in ("tk-0001", "tk-0002", "adv-001"):
            assert (FIXTURES_DIR / source / f"{ticket_id}.json").exists()


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: f"{p.parent.name}/{p.stem}")
async def test_fixture_segue_o_contrato(path):
    source, ticket_id = path.parent.name, path.stem
    fixture = load_fixture(path)
    provider = ReplayProvider(source, simulate_latency=False)

    assert fixture["ticket_id"] == ticket_id
    assert set(fixture["nodes"]) <= DECISION_NODES
    assert ("reply" in fixture) == (source == "llm" and "triage" in fixture["nodes"])
    for node in fixture["nodes"]:
        result = await provider.decide(
            NodeSpec(name=node, state_fields=[], questions=[]), {"ticket_id": ticket_id}
        )
        assert result.provider == source


def test_fixtures_sao_de_tickets_do_golden_set():
    ids = {t.id for t in load_golden_set()}

    assert {path.stem for path in FIXTURES} <= ids
