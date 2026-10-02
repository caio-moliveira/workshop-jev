"""API do backend: configuração, dataset, tools, execução de uma pergunta e de lotes, com
SSE (PRD 11)."""

from collections.abc import AsyncIterable
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field, model_validator

from app.batches import MAX_BATCH, estimate_cost, export_csv, run_batch, select_questions
from app.config import GraphConfig, ProviderName, load_config
from app.dataset import Question, QuestionInput, load_golden_set
from app.graph import RunResult, build_providers, new_run_id, run_question
from app.metrics.aggregator import BatchReport
from app.metrics.pricing import Pricing, load_pricing
from app.providers.replay import FIXTURES_DIR, has_fixture
from app.runs import EventChannel, Registry
from app.store import RUNS_DIR, RunStore
from app.tools import TOOLS, Tool


class AppState:
    def __init__(self, runs_dir: Path, simulate_latency: bool, fixtures_dir: Path):
        # PUT /config vale em memória: graph.yaml só muda por commit `config:`.
        self.config = load_config()
        self.runs = Registry()
        self.batches = Registry()
        self.store = RunStore(runs_dir)
        self.simulate_latency = simulate_latency
        self.fixtures_dir = fixtures_dir

    def providers(self, config: GraphConfig):
        return build_providers(config, self.simulate_latency, self.fixtures_dir)


def get_state(request: Request) -> AppState:
    return request.app.state.jev


StateDep = Annotated[AppState, Depends(get_state)]


# Canais resolvidos antes de abrir o stream: dentro do gerador o 404 já não chega ao cliente.


def get_run_channel(run_id: str, state: StateDep) -> EventChannel:
    channel = state.runs.get(run_id)
    if channel is None:
        raise HTTPException(404, f"execução {run_id} não encontrada")
    return channel


def get_batch_channel(batch_id: str, state: StateDep) -> EventChannel:
    channel = state.batches.get(batch_id)
    if channel is None:
        raise HTTPException(404, f"lote {batch_id} não encontrado")
    return channel


RunChannelDep = Annotated[EventChannel, Depends(get_run_channel)]
BatchChannelDep = Annotated[EventChannel, Depends(get_batch_channel)]


class RunRequest(BaseModel):
    question_id: str | None = None
    text: str | None = None
    # Lado a lado: o provider que decide todas as etapas desta execução. Sem ele, vale /config.
    pipeline: ProviderName | None = None

    @model_validator(mode="after")
    def one_source(self):
        if (self.question_id is None) == (self.text is None):
            raise ValueError("informe question_id ou text, um dos dois")
        return self


class RunCreated(BaseModel):
    run_id: str


class DatasetQuestion(Question):
    replayable: bool


class BatchRequest(BaseModel):
    n: int = Field(default=100, ge=1, le=MAX_BATCH)
    tag: str | None = None


class BatchEstimate(BaseModel):
    n: int  # quantas perguntas vão rodar de fato (em replay, só os que têm gravação)
    estimated_cost_usd: float | None


class BatchCreated(BatchEstimate):
    batch_id: str


async def stream(channel: EventChannel) -> AsyncIterable[ServerSentEvent]:
    async for event in channel.subscribe():
        yield ServerSentEvent(data=event.model_dump(mode="json"), event=event.type)


def create_app(
    runs_dir: Path = RUNS_DIR, simulate_latency: bool = True, fixtures_dir: Path = FIXTURES_DIR
) -> FastAPI:
    app = FastAPI(title="JEV Jornada")
    app.state.jev = AppState(runs_dir, simulate_latency, fixtures_dir)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
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

    @app.get("/tools")
    def get_tools() -> list[Tool]:
        return list(TOOLS.values())

    @app.get("/dataset")
    def get_dataset(
        state: StateDep,
        tag: Annotated[str | None, Query()] = None,
        limit: Annotated[int | None, Query(ge=1)] = None,
    ) -> list[DatasetQuestion]:
        return [
            DatasetQuestion(**q.model_dump(), replayable=has_fixture(q.id, state.fixtures_dir))
            for q in load_golden_set(tag=tag, limit=limit)
        ]

    @app.post("/runs", status_code=status.HTTP_202_ACCEPTED)
    async def post_run(request: RunRequest, state: StateDep) -> RunCreated:
        config = state.config
        if request.pipeline is not None:
            config = config.for_pipeline(request.pipeline)
        run_id = new_run_id()
        if request.text is not None:
            if config.mode == "replay":
                raise HTTPException(422, "modo replay só executa perguntas do golden set")
            question = QuestionInput(id=f"adhoc-{run_id}", text=request.text)
        else:
            question = next((q for q in load_golden_set() if q.id == request.question_id), None)
            if question is None:
                raise HTTPException(404, f"pergunta {request.question_id} não está no golden set")
            if config.mode == "replay" and not has_fixture(question.id, state.fixtures_dir):
                raise HTTPException(422, f"sem gravação de replay para {question.id}")

        channel = state.runs.open(run_id)
        state.runs.spawn(execute(state, channel, question, config, run_id))
        return RunCreated(run_id=run_id)

    @app.get("/runs/{run_id}/events", response_class=EventSourceResponse)
    async def run_events(channel: RunChannelDep) -> AsyncIterable[ServerSentEvent]:
        async for event in stream(channel):
            yield event

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str, state: StateDep) -> RunResult:
        channel = state.runs.get(run_id)
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

    @app.get("/batches/estimate")
    def get_batch_estimate(
        state: StateDep,
        n: Annotated[int, Query(ge=1, le=MAX_BATCH)] = 100,
        tag: Annotated[str | None, Query()] = None,
    ) -> BatchEstimate:
        count = len(select_questions(state.config, n, tag, state.fixtures_dir))
        cost = estimate_cost(state.config, count, load_pricing(), state.fixtures_dir)
        return BatchEstimate(n=count, estimated_cost_usd=cost)

    @app.post("/batches", status_code=status.HTTP_202_ACCEPTED)
    async def post_batch(request: BatchRequest, state: StateDep) -> BatchCreated:
        # A configuração é copiada: PUT /config durante o lote não afeta este lote.
        config = state.config.model_copy(deep=True)
        questions = select_questions(config, request.n, request.tag, state.fixtures_dir)
        if not questions:
            raise HTTPException(422, "nenhuma pergunta para executar com esse filtro")
        batch_id = new_run_id()
        channel = state.batches.open(batch_id)
        state.batches.spawn(
            run_batch(batch_id, questions, config, state.providers(config), state.store, channel)
        )
        cost = estimate_cost(config, len(questions), load_pricing(), state.fixtures_dir)
        return BatchCreated(batch_id=batch_id, n=len(questions), estimated_cost_usd=cost)

    @app.get("/batches/{batch_id}/events", response_class=EventSourceResponse)
    async def batch_events(channel: BatchChannelDep) -> AsyncIterable[ServerSentEvent]:
        async for event in stream(channel):
            yield event

    @app.get("/batches/{batch_id}/report")
    def get_batch_report(batch_id: str, state: StateDep) -> BatchReport:
        return load_report(state, batch_id)

    @app.get("/batches/{batch_id}/export")
    def export_batch(
        batch_id: str, state: StateDep, format: Annotated[Literal["csv", "json"], Query()] = "json"
    ) -> Response:
        report = load_report(state, batch_id)
        filename = f"lote-{batch_id}.{format}"
        if format == "json":
            body, media_type = report.model_dump_json(indent=2), "application/json"
        else:
            channel = state.batches.get(batch_id)
            results = channel.extra.get("results") if channel else None
            results = results or state.store.runs_for_batch(batch_id)
            body, media_type = export_csv(report, results), "text/csv; charset=utf-8"
        return Response(
            body,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


def load_report(state: AppState, batch_id: str) -> BatchReport:
    channel = state.batches.get(batch_id)
    if channel is not None and not channel.done:
        raise HTTPException(409, f"lote {batch_id} ainda em andamento")
    if channel is not None and channel.result is not None:
        return channel.result
    saved = state.store.load_report(batch_id)
    if saved is None:
        raise HTTPException(404, f"lote {batch_id} não encontrado")
    return BatchReport.model_validate_json(saved)


async def execute(
    state: AppState,
    channel: EventChannel,
    question: QuestionInput,
    config: GraphConfig,
    run_id: str,
) -> None:
    try:
        result = await run_question(
            question, config, emit=channel.publish, providers=state.providers(config), run_id=run_id
        )
    except Exception as error:
        await channel.finish(error=f"{type(error).__name__}: {error}")
        raise
    state.store.save_run(result)
    await channel.finish(result=result)


app = create_app()
