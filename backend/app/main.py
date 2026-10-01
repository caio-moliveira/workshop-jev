"""API do backend: configuração, dataset e execução de um ticket com SSE (PRD 11)."""

from collections.abc import AsyncIterable
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, model_validator

from app.config import GraphConfig, load_config
from app.dataset import Ticket, TicketInput, load_golden_set
from app.graph import RunResult, new_run_id, run_ticket
from app.metrics.pricing import Pricing, load_pricing
from app.providers.replay import has_fixture
from app.runs import RunChannel, RunRegistry
from app.store import RUNS_DIR, RunStore


class AppState:
    def __init__(self, runs_dir: Path, simulate_latency: bool):
        # PUT /config vale em memória: graph.yaml só muda por commit `config:`.
        self.config = load_config()
        self.registry = RunRegistry()
        self.store = RunStore(runs_dir)
        self.simulate_latency = simulate_latency


def get_state(request: Request) -> AppState:
    return request.app.state.jev


StateDep = Annotated[AppState, Depends(get_state)]


def get_channel(run_id: str, state: StateDep) -> RunChannel:
    # Resolvido antes de abrir o stream: dentro do gerador o 404 já não chega ao cliente.
    channel = state.registry.get(run_id)
    if channel is None:
        raise HTTPException(404, f"execução {run_id} não encontrada")
    return channel


ChannelDep = Annotated[RunChannel, Depends(get_channel)]


class RunRequest(BaseModel):
    ticket_id: str | None = None
    text: str | None = None

    @model_validator(mode="after")
    def one_source(self):
        if (self.ticket_id is None) == (self.text is None):
            raise ValueError("informe ticket_id ou text, um dos dois")
        return self


class RunCreated(BaseModel):
    run_id: str


class DatasetTicket(Ticket):
    replayable: bool


def create_app(runs_dir: Path = RUNS_DIR, simulate_latency: bool = True) -> FastAPI:
    app = FastAPI(title="JEV Jornada")
    app.state.jev = AppState(runs_dir, simulate_latency)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/config")
    async def get_config(state: StateDep) -> GraphConfig:
        return state.config

    @app.put("/config")
    async def put_config(config: GraphConfig, state: StateDep) -> GraphConfig:
        state.config = config
        return config

    @app.get("/pricing")
    def get_pricing() -> Pricing:
        return load_pricing()

    @app.get("/dataset")
    def get_dataset(
        tag: Annotated[str | None, Query()] = None,
        limit: Annotated[int | None, Query(ge=1)] = None,
    ) -> list[DatasetTicket]:
        return [
            DatasetTicket(**t.model_dump(), replayable=has_fixture(t.id))
            for t in load_golden_set(tag=tag, limit=limit)
        ]

    @app.post("/runs", status_code=status.HTTP_202_ACCEPTED)
    async def post_run(request: RunRequest, state: StateDep) -> RunCreated:
        config = state.config
        run_id = new_run_id()
        if request.text is not None:
            if config.mode == "replay":
                raise HTTPException(422, "modo replay só executa tickets do golden set")
            ticket = TicketInput(id=f"adhoc-{run_id}", text=request.text)
        else:
            ticket = next((t for t in load_golden_set() if t.id == request.ticket_id), None)
            if ticket is None:
                raise HTTPException(404, f"ticket {request.ticket_id} não está no golden set")
            if config.mode == "replay" and not has_fixture(ticket.id):
                raise HTTPException(422, f"sem gravação de replay para {ticket.id}")

        channel = state.registry.open(run_id)
        state.registry.spawn(execute(state, channel, ticket, config, run_id))
        return RunCreated(run_id=run_id)

    @app.get("/runs/{run_id}/events", response_class=EventSourceResponse)
    async def run_events(channel: ChannelDep) -> AsyncIterable[ServerSentEvent]:
        async for event in channel.subscribe():
            yield ServerSentEvent(data=event.model_dump(mode="json"), event=event.type)

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str, state: StateDep) -> RunResult:
        channel = state.registry.get(run_id)
        if channel is not None:
            if not channel.done:
                raise HTTPException(409, f"execução {run_id} ainda em andamento")
            if channel.error is not None:
                raise HTTPException(500, channel.error)
            return channel.result
        result = state.store.get_run(run_id)
        if result is None:
            raise HTTPException(404, f"execução {run_id} não encontrada")
        return result

    return app


async def execute(
    state: AppState, channel: RunChannel, ticket: TicketInput, config: GraphConfig, run_id: str
) -> None:
    try:
        result = await run_ticket(
            ticket,
            config,
            emit=channel.publish,
            simulate_latency=state.simulate_latency,
            run_id=run_id,
        )
    except Exception as error:
        await channel.finish(error=f"{type(error).__name__}: {error}")
        raise
    state.store.save_run(result)
    await channel.finish(result=result)


app = create_app()
