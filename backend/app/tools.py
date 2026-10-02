"""As tools do agente de vendas: cada uma lê uma view do banco (SPEC-08).

O nome da view vem sempre deste registro, nunca do modelo: a triagem escolhe o nome de uma
tool entre as opções, e o código traduz para a view. As `description` são os critérios da
pergunta `tool` da triagem, a mesma fonte para Jev e LLM.
"""

import asyncio
import json
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import asyncpg
from pydantic import BaseModel

from app.config import database_url
from app.providers.replay import FIXTURES_DIR, ReplayMissError

MAX_ROWS = 50
NO_TOOL = "nenhuma"
TOOLS_FIXTURES_DIR = "tools"


class Tool(BaseModel):
    name: str
    view: str
    title: str
    description: str


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            name="vendas_mensal",
            view="vw_vendas_mensal",
            title="Vendas por mês",
            description=(
                "Receita, número de pedidos, ticket médio e variação de cada mês, de jan/2025 "
                "a set/2026. Para evolução no tempo, sazonalidade e comparação entre meses."
            ),
        ),
        Tool(
            name="vendas_por_categoria",
            view="vw_vendas_por_categoria",
            title="Vendas por categoria",
            description=(
                "Receita, unidades, margem e participação de cada categoria de produto em 2026."
            ),
        ),
        Tool(
            name="top_produtos",
            view="vw_top_produtos",
            title="Produtos mais vendidos",
            description="Os 10 produtos de maior receita em 2026, com categoria e unidades.",
        ),
        Tool(
            name="vendas_por_vendedor",
            view="vw_vendas_por_vendedor",
            title="Vendas por vendedor",
            description=(
                "Receita, pedidos, meta e atingimento da meta de cada vendedor em 2026, com a "
                "região de cada um. Para ranking de vendedores e quem bateu a meta."
            ),
        ),
        Tool(
            name="vendas_por_regiao",
            view="vw_vendas_por_regiao",
            title="Vendas por região",
            description=(
                "Receita, pedidos, clientes ativos e participação de cada região do país em 2026."
            ),
        ),
        Tool(
            name="top_clientes",
            view="vw_top_clientes",
            title="Maiores clientes",
            description=(
                "Os 10 clientes (empresas) de maior receita em 2026, com segmento, região, "
                "pedidos e data da última compra."
            ),
        ),
        Tool(
            name="kpis",
            view="vw_kpis",
            title="Indicadores gerais",
            description=(
                "Números consolidados de jan a set de 2026: receita total, receita do mesmo "
                "período de 2025, crescimento, pedidos, ticket médio, clientes ativos, "
                "atingimento da meta da empresa, taxa de cancelamento e margem bruta."
            ),
        ),
    )
}


class ToolResult(BaseModel):
    tool: str
    view: str
    columns: list[str]
    rows: list[dict[str, str | int | float | None]]
    row_count: int
    truncated: bool
    latency_ms: float


class UnknownToolError(Exception):
    """A tool não está no registro."""


class ToolRunner(Protocol):
    async def run(self, tool: str) -> ToolResult: ...


def lookup(name: str) -> Tool:
    tool = TOOLS.get(name)
    if tool is None:
        raise UnknownToolError(f"tool desconhecida: {name!r}")
    return tool


def to_json_value(value) -> str | int | float | None:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


class PostgresToolRunner:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or database_url()
        self.pool: asyncpg.Pool | None = None

    async def run(self, tool: str) -> ToolResult:
        spec = lookup(tool)  # antes de qualquer SQL
        if self.pool is None:
            # Criado na primeira chamada, dentro do event loop que vai usá-lo.
            self.pool = await asyncpg.create_pool(
                self.dsn, min_size=1, max_size=5, command_timeout=5
            )
        sql = f"SELECT * FROM {spec.view} LIMIT $1"  # noqa: S608 - view do registro, não do modelo

        start = time.perf_counter()
        async with self.pool.acquire() as conn:
            records = await conn.fetch(sql, MAX_ROWS + 1)
        latency_ms = (time.perf_counter() - start) * 1000

        truncated = len(records) > MAX_ROWS
        records = records[:MAX_ROWS]
        columns = list(records[0].keys()) if records else []
        rows = [{k: to_json_value(v) for k, v in r.items()} for r in records]
        return ToolResult(
            tool=spec.name,
            view=spec.view,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            latency_ms=latency_ms,
        )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None


class ReplayToolRunner:
    def __init__(self, simulate_latency: bool = True, fixtures_dir: Path = FIXTURES_DIR):
        self.simulate_latency = simulate_latency
        self.fixtures_dir = fixtures_dir

    async def run(self, tool: str) -> ToolResult:
        lookup(tool)
        path = tool_fixture_path(tool, self.fixtures_dir)
        if not path.exists():
            raise ReplayMissError(f"sem gravação da tool {tool}")
        result = ToolResult.model_validate_json(path.read_text(encoding="utf-8"))
        if self.simulate_latency:
            await asyncio.sleep(result.latency_ms / 1000)
        return result


def tool_fixture_path(tool: str, fixtures_dir: Path = FIXTURES_DIR) -> Path:
    return fixtures_dir / TOOLS_FIXTURES_DIR / f"{tool}.json"


def write_tool_fixture(result: ToolResult, fixtures_dir: Path = FIXTURES_DIR) -> Path:
    path = tool_fixture_path(result.tool, fixtures_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = result.model_dump(mode="json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
