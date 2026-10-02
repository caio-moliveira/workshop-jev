"""Invariantes do banco de vendas (SPEC-07). Precisam do Postgres do docker-compose:

docker compose up -d --wait
uv run pytest -m db
"""

import asyncpg
import pytest

from app.config import database_url

pytestmark = pytest.mark.db

TABLES = {
    "regioes",
    "categorias",
    "produtos",
    "vendedores",
    "clientes",
    "pedidos",
    "itens_pedido",
    "metas",
}
VIEWS = {
    "vw_vendas_mensal",
    "vw_vendas_por_categoria",
    "vw_top_produtos",
    "vw_vendas_por_vendedor",
    "vw_vendas_por_regiao",
    "vw_top_clientes",
    "vw_kpis",
}


@pytest.fixture
async def conn():
    connection = await asyncpg.connect(database_url())
    yield connection
    await connection.close()


async def test_schema_has_tables_and_views(conn):
    tables = {r["tablename"] for r in await conn.fetch("SELECT tablename FROM pg_tables")}
    views = {r["viewname"] for r in await conn.fetch("SELECT viewname FROM pg_views")}
    assert tables >= TABLES
    assert views >= VIEWS


async def test_views_are_small(conn):
    for view in VIEWS:
        count = await conn.fetchval(f"SELECT count(*) FROM {view}")  # noqa: S608 - nome fixo
        assert 0 < count <= 25, view


async def test_revenue_agrees_across_views(conn):
    kpi = await conn.fetchval("SELECT valor FROM vw_kpis WHERE indicador = 'Receita jan-set 2026'")
    by_category = await conn.fetchval("SELECT sum(receita) FROM vw_vendas_por_categoria")
    by_region = await conn.fetchval("SELECT sum(receita) FROM vw_vendas_por_regiao")
    by_seller = await conn.fetchval("SELECT sum(receita) FROM vw_vendas_por_vendedor")
    by_month = await conn.fetchval(
        "SELECT sum(receita) FROM vw_vendas_mensal WHERE mes BETWEEN '2026-01' AND '2026-09'"
    )
    # Cada view arredonda por linha: a soma pode diferir de centavos.
    for total in (by_category, by_region, by_seller, by_month):
        assert abs(total - kpi) < 1


async def test_app_user_cannot_read_tables(conn):
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await conn.fetch("SELECT * FROM pedidos LIMIT 1")


async def test_app_user_cannot_write(conn):
    with pytest.raises((asyncpg.ReadOnlySQLTransactionError, asyncpg.InsufficientPrivilegeError)):
        await conn.execute("INSERT INTO regioes (id, nome) VALUES (99, 'Teste')")
    with pytest.raises((asyncpg.ReadOnlySQLTransactionError, asyncpg.InsufficientPrivilegeError)):
        await conn.execute("CREATE TABLE intrusa (id int)")
