import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client(tmp_path, monkeypatch):
    for key in ("TYPESAFE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PROVIDER_MODE", "replay")
    app = create_app(runs_dir=tmp_path / "runs", simulate_latency=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.runs_dir = tmp_path / "runs"
        yield client


def parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "data" in fields:
            events.append({"event": fields.get("event"), "data": json.loads(fields["data"])})
    return events


async def start_run(client, ticket_id="tk-0001") -> str:
    response = await client.post("/runs", json={"ticket_id": ticket_id})
    assert response.status_code == 202
    return response.json()["run_id"]


async def wait_finished(client, run_id: str) -> dict:
    for _ in range(100):
        response = await client.get(f"/runs/{run_id}")
        if response.status_code == 200:
            return response.json()
        assert response.status_code == 409
        await asyncio.sleep(0.02)
    raise AssertionError("a execução não terminou")


async def test_health(client):
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_executa_um_ticket_e_transmite_os_eventos_em_ordem(client):
    run_id = await start_run(client)

    response = await client.get(f"/runs/{run_id}/events")

    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    types = [e["event"] for e in events]
    assert types[0] == "run.started"
    assert types[-1] == "run.finished"
    assert types[1:5] == ["node.started", "provider.finished", "provider.finished", "node.finished"]
    assert all(e["data"]["run_id"] == run_id for e in events)
    nodes = [e["data"]["node"] for e in events if e["event"] == "node.started"]
    assert nodes == ["guardrail", "triage", "reply", "verify", "act"]


async def test_resultado_e_o_mesmo_do_evento_final(client):
    run_id = await start_run(client)
    events = parse_sse((await client.get(f"/runs/{run_id}/events")).text)

    result = await wait_finished(client, run_id)

    assert result == events[-1]["data"]["data"]
    assert result["action"] == "auto"
    assert result["mode"] == "replay"


async def test_quem_conecta_depois_do_fim_recebe_todos_os_eventos(client):
    run_id = await start_run(client, "adv-001")
    await wait_finished(client, run_id)

    events = parse_sse((await client.get(f"/runs/{run_id}/events")).text)

    assert [e["event"] for e in events] == [
        "run.started",
        "node.started",
        "provider.finished",
        "provider.finished",
        "node.finished",
        "run.finished",
    ]


async def test_execucao_desconhecida_e_404(client):
    assert (await client.get("/runs/nao-existe")).status_code == 404
    assert (await client.get("/runs/nao-existe/events")).status_code == 404


async def test_put_config_muda_os_providers_da_proxima_execucao(client):
    config = (await client.get("/config")).json()
    config["providers"]["triage"] = "llm"

    assert (await client.put("/config", json=config)).status_code == 200
    run_id = await start_run(client)
    events = parse_sse((await client.get(f"/runs/{run_id}/events")).text)

    triage = [
        e for e in events if e["event"] == "provider.finished" and e["data"]["node"] == "triage"
    ]
    assert len(triage) == 1
    assert (await client.get("/config")).json()["providers"]["triage"] == "llm"


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c["thresholds"].update(guardrail_block=1.5),
        lambda c: c["providers"].update(triage="gpt"),
        lambda c: c.update(primary="ambos"),
    ],
)
async def test_put_config_invalida_e_422(client, change):
    config = (await client.get("/config")).json()
    change(config)

    assert (await client.put("/config", json=config)).status_code == 422


async def test_config_traz_o_catalogo_de_modelos(client):
    config = (await client.get("/config")).json()

    assert len(config["catalog"]) == 8
    assert config["mode"] == "replay"


async def test_pricing(client):
    pricing = (await client.get("/pricing")).json()

    assert pricing["models"]["jev-1.13.0"] == {"input": 0.042, "output": 0}


async def test_dataset_filtra_por_tag_e_limita(client):
    tickets = (await client.get("/dataset", params={"tag": "churn", "limit": 5})).json()

    assert len(tickets) == 5
    assert all("churn" in t["tags"] for t in tickets)


async def test_dataset_indica_quais_tickets_tem_gravacao(client):
    tickets = (await client.get("/dataset", params={"limit": 3})).json()

    assert [t["replayable"] for t in tickets] == [True, True, False]


async def test_ticket_digitado_em_replay_e_422(client):
    response = await client.post("/runs", json={"text": "Quero meu dinheiro de volta"})

    assert response.status_code == 422
    assert "golden set" in response.json()["detail"]


async def test_ticket_sem_gravacao_em_replay_e_422(client):
    assert (await client.post("/runs", json={"ticket_id": "tk-0300"})).status_code == 422


async def test_ticket_inexistente_e_404(client):
    assert (await client.post("/runs", json={"ticket_id": "tk-9999"})).status_code == 404


async def test_pedido_sem_ticket_nem_texto_e_422(client):
    assert (await client.post("/runs", json={})).status_code == 422


async def test_execucao_concluida_vira_linha_no_jsonl(client):
    run_id = await start_run(client)
    await wait_finished(client, run_id)

    lines = (client.runs_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["run_id"] == run_id
    assert saved["config_version"] == "1"


async def test_resultado_sobrevive_ao_reinicio_pelo_jsonl(client):
    run_id = await start_run(client)
    await wait_finished(client, run_id)

    restarted = create_app(runs_dir=client.runs_dir, simulate_latency=False)
    async with AsyncClient(transport=ASGITransport(app=restarted), base_url="http://test") as c:
        assert (await c.get(f"/runs/{run_id}")).json()["run_id"] == run_id
