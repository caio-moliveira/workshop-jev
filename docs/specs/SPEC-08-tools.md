Status: aceita

# SPEC-08: Tools

## Objetivo

Expor as views do banco de vendas como tools com nome fixo, lidas pela aplicação com segurança em modo live e reproduzidas de gravação em modo replay.

## Cobre do PRD

Seções 5 (node `tool`), 5.1, 7.1 e 11 (`/tools`). RF-11 (replay sem banco), RF-15.

## Interfaces

### `backend/app/tools.py`

```python
class Tool(BaseModel):
    name: str            # "vendas_mensal"
    view: str            # "vw_vendas_mensal"
    title: str           # "Vendas por mês"
    description: str     # critério da opção na pergunta `tool` da triagem

TOOLS: dict[str, Tool]   # as 7 tools do PRD 5.1
NO_TOOL = "nenhuma"
MAX_ROWS = 50

class ToolResult(BaseModel):
    tool: str
    view: str
    columns: list[str]
    rows: list[dict[str, str | int | float | None]]
    row_count: int
    truncated: bool
    latency_ms: float

class ToolRunner(Protocol):
    async def run(self, tool: str) -> ToolResult: ...

class PostgresToolRunner: ...   # asyncpg, live
class ReplayToolRunner: ...     # fixtures/replay/tools/<tool>.json
class UnknownToolError(Exception): ...
```

- O SQL é sempre `SELECT * FROM <TOOLS[tool].view> LIMIT $1`, com `MAX_ROWS + 1` para marcar `truncated`. Nome de tool fora de `TOOLS` levanta `UnknownToolError` antes de montar qualquer SQL. Nada vindo do modelo vira SQL.
- `PostgresToolRunner` cria o pool na primeira chamada, dentro do event loop em uso, com `command_timeout`. `Decimal` vira `float` e `date` vira texto ISO.
- Latência com `time.perf_counter()` ao redor da consulta.
- `ReplayToolRunner` levanta `ReplayMissError` se não há gravação da tool, e simula a latência gravada quando pedido.
- Driver: `asyncpg` (o psycopg assíncrono não roda no `ProactorEventLoop` do Windows).

### `backend/app/config.py`

`database_url() -> str`: `DATABASE_URL` do ambiente, ou `postgresql://jev_app:jev_app@localhost:5433/vendas`, que aponta para o compose da SPEC-07.

### Gravação

`fixtures/replay/tools/<tool>.json` guarda um `ToolResult`. Como as views não têm parâmetro, uma gravação por tool serve a qualquer pergunta e a qualquer primário.

```
uv run python -m app.cli snapshot      # precisa só do banco; grava as 7 tools
```

### API

`GET /tools -> list[Tool]`.

## Critérios de aceite

- [ ] Toda view de `TOOLS` existe em `db/init/03_views.sql` (teste estático, sem banco).
- [ ] `UnknownToolError` para tool fora do registro, sem consulta ao banco.
- [ ] `ReplayToolRunner` devolve o `ToolResult` gravado e levanta `ReplayMissError` sem gravação.
- [ ] As 7 gravações de `fixtures/replay/tools/` validam como `ToolResult`.
- [ ] Os globs de fixtures de `batches.estimate_cost` e `tests/test_fixtures.py` ignoram `tools/`.
- [ ] `GET /tools` devolve as 7 tools.
- [ ] Com banco (marcador `db`): `PostgresToolRunner` lê cada view, `truncated` é falso e `row_count` bate com a view.

## Fora

- Usar as tools no grafo: SPEC-09.
- Tools com parâmetros, SQL gerado pelo modelo e tool calling nativo: fora do projeto.
