import csv
import io
import json
import shutil
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.dataset import load_golden_set
from app.main import create_app
from app.metrics.aggregator import BatchReport
from app.providers.replay import FIXTURES_DIR

from .test_api import parse_sse


def copy_fixtures(target, question_ids):
    """Fixtures descartáveis: a gravação da q-001 reaproveitada para outras perguntas.
    Só para exercitar o lote; não é dado de comparação."""
    for source in ("jev", "llm"):
        recorded = json.loads((FIXTURES_DIR / source / "q-001.json").read_text(encoding="utf-8"))
        (target / source).mkdir(parents=True, exist_ok=True)
        for question_id in question_ids:
            fixture = recorded | {"question_id": question_id}
            (target / source / f"{question_id}.json").write_text(json.dumps(fixture), "utf-8")
        shutil.copy(FIXTURES_DIR / source / "adv-001.json", target / source / "adv-001.json")
    shutil.copytree(FIXTURES_DIR / "tools", target / "tools")


@pytest.fixture
async def client(tmp_path, monkeypatch):
    for key in ("TYPESAFE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PROVIDER_MODE", "replay")
    ids = [q.id for q in load_golden_set() if q.id.startswith("q-")]
    copy_fixtures(tmp_path / "fixtures", ids)
    app = create_app(
        runs_dir=tmp_path / "runs", simulate_latency=False, fixtures_dir=tmp_path / "fixtures"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.runs_dir = tmp_path / "runs"
        yield client


async def start(client, **body) -> dict:
    response = await client.post("/batches", json=body)
    assert response.status_code == 202, response.text
    return response.json()


async def test_lote_de_10_transmite_o_progresso_e_o_relatorio(client):
    created = await start(client, n=10)

    events = parse_sse((await client.get(f"/batches/{created['batch_id']}/events")).text)

    types = [e["event"] for e in events]
    assert types[0] == "batch.started"
    assert types.count("batch.progress") == 10
    assert types[-1] == "batch.finished"
    assert [e["data"]["data"]["done"] for e in events if e["event"] == "batch.progress"] == list(
        range(1, 11)
    )
    report = (await client.get(f"/batches/{created['batch_id']}/report")).json()
    assert report["n"] == 10
    assert report["config_version"] == "2"
    assert report == events[-1]["data"]["data"]


async def test_n_acima_do_golden_set_e_422(client):
    assert (await client.post("/batches", json={"n": 1000})).status_code == 422


async def test_filtro_por_tag(client):
    created = await start(client, n=3, tag="meta")

    await client.get(f"/batches/{created['batch_id']}/events")
    report = (await client.get(f"/batches/{created['batch_id']}/report")).json()

    assert report["n"] == 3
    assert all("meta" in row["tags"] for row in report["questions"])


async def test_estimativa_de_custo_antes_de_rodar(client):
    estimate = (await client.get("/batches/estimate", params={"n": 10})).json()

    assert estimate["n"] == 10
    assert estimate["estimated_cost_usd"] > 0


async def test_estimativa_sem_preco_do_modelo_e_nula(client):
    config = (await client.get("/config")).json()
    config["llm_model"] = "anthropic:modelo-fora-da-tabela"
    assert (await client.put("/config", json=config)).status_code == 200

    estimate = (await client.get("/batches/estimate", params={"n": 10})).json()

    assert estimate["estimated_cost_usd"] is None


async def test_exporta_csv_e_json(client):
    created = await start(client, n=10)
    batch_id = created["batch_id"]
    await client.get(f"/batches/{batch_id}/events")

    as_json = await client.get(f"/batches/{batch_id}/export", params={"format": "json"})
    as_csv = await client.get(f"/batches/{batch_id}/export", params={"format": "csv"})

    assert BatchReport.model_validate_json(as_json.text).config_version == "2"
    assert "attachment" in as_csv.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(as_csv.text)))
    # por pergunta: 3 do guardrail + 1 da triagem + 3 da verificação, para cada provider
    assert len(rows) == 10 * (3 + 1 + 3) * 2
    assert {row["config_version"] for row in rows} == {"2"}
    assert {row["provider"] for row in rows} == {"jev", "llm"}


async def test_relatorio_sobrevive_ao_reinicio(client, tmp_path):
    created = await start(client, n=3)
    await client.get(f"/batches/{created['batch_id']}/events")

    restarted = create_app(
        runs_dir=client.runs_dir, simulate_latency=False, fixtures_dir=tmp_path / "fixtures"
    )
    async with AsyncClient(transport=ASGITransport(app=restarted), base_url="http://test") as c:
        report = await c.get(f"/batches/{created['batch_id']}/report")
        exported = await c.get(f"/batches/{created['batch_id']}/export", params={"format": "csv"})

    assert report.json()["n"] == 3
    assert len(list(csv.DictReader(io.StringIO(exported.text)))) == 3 * 7 * 2


async def test_lote_inteiro_em_replay_termina_rapido(client):
    start_time = time.perf_counter()
    created = await start(client, n=100)
    await client.get(f"/batches/{created['batch_id']}/events")

    assert time.perf_counter() - start_time < 10
    assert (await client.get(f"/batches/{created['batch_id']}/report")).json()["n"] == 61


async def test_lote_desconhecido_e_404(client):
    assert (await client.get("/batches/nao-existe/report")).status_code == 404
    assert (await client.get("/batches/nao-existe/events")).status_code == 404
