"""Registro de tools, replay das tools e GET /tools (SPEC-08). Sem banco, exceto o marcado."""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.providers.replay import FIXTURES_DIR, ReplayMissError
from app.tools import (
    MAX_ROWS,
    TOOLS,
    PostgresToolRunner,
    ReplayToolRunner,
    ToolResult,
    UnknownToolError,
    to_json_value,
    tool_fixture_path,
    write_tool_fixture,
)

VIEWS_SQL = Path(__file__).resolve().parents[2] / "db" / "init" / "03_views.sql"

RESULT = ToolResult(
    tool="kpis",
    view="vw_kpis",
    columns=["indicador", "valor", "unidade"],
    rows=[{"indicador": "Receita jan-set 2026", "valor": 100.0, "unidade": "BRL"}],
    row_count=1,
    truncated=False,
    latency_ms=12.5,
)


def test_every_registered_view_exists_in_init_sql():
    created = set(re.findall(r"CREATE VIEW (\w+)", VIEWS_SQL.read_text(encoding="utf-8")))
    assert {tool.view for tool in TOOLS.values()} <= created


def test_registry_has_the_seven_tools():
    assert set(TOOLS) == {
        "vendas_mensal",
        "vendas_por_categoria",
        "top_produtos",
        "vendas_por_vendedor",
        "vendas_por_regiao",
        "top_clientes",
        "kpis",
    }


async def test_unknown_tool_fails_before_touching_the_database():
    runner = PostgresToolRunner(dsn="postgresql://ninguem@127.0.0.1:1/nada")
    with pytest.raises(UnknownToolError):
        await runner.run("vw_kpis; DROP TABLE pedidos")
    assert runner.pool is None


def test_values_become_json():
    assert to_json_value(Decimal("12.50")) == 12.5
    assert to_json_value(date(2026, 9, 30)) == "2026-09-30"
    assert to_json_value("Sul") == "Sul"
    assert to_json_value(None) is None


async def test_replay_returns_recorded_result(tmp_path):
    write_tool_fixture(RESULT, tmp_path)
    runner = ReplayToolRunner(simulate_latency=False, fixtures_dir=tmp_path)
    assert await runner.run("kpis") == RESULT


async def test_replay_without_recording_raises(tmp_path):
    runner = ReplayToolRunner(simulate_latency=False, fixtures_dir=tmp_path)
    with pytest.raises(ReplayMissError):
        await runner.run("kpis")
    with pytest.raises(UnknownToolError):
        await runner.run("nao_existe")


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_versioned_tool_recordings_follow_the_contract(name):
    path = tool_fixture_path(name, FIXTURES_DIR)
    result = ToolResult.model_validate_json(path.read_text(encoding="utf-8"))
    assert result.tool == name
    assert result.view == TOOLS[name].view
    assert result.row_count == len(result.rows) <= 25
    assert not result.truncated
    assert all(set(row) == set(result.columns) for row in result.rows)


async def test_get_tools(monkeypatch, tmp_path):
    monkeypatch.setenv("PROVIDER_MODE", "replay")
    app = create_app(runs_dir=tmp_path / "runs", simulate_latency=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/tools")
    assert response.status_code == 200
    body = response.json()
    assert [t["name"] for t in body] == list(TOOLS)
    assert all(t["view"].startswith("vw_") and t["description"] for t in body)


@pytest.mark.db
@pytest.mark.parametrize("name", sorted(TOOLS))
async def test_postgres_runner_reads_each_view(name):
    runner = PostgresToolRunner()
    try:
        result = await runner.run(name)
    finally:
        await runner.close()
    assert result.view == TOOLS[name].view
    assert 0 < result.row_count <= MAX_ROWS
    assert not result.truncated
    assert result.latency_ms > 0
