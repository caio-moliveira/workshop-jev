"""O seed do banco de vendas é reproduzível e cabe no pre-commit (SPEC-07). Sem banco."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "data" / "scripts" / "generate_sales_seed.py"
SEED_SQL = ROOT / "db" / "init" / "02_seed.sql"


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_sales_seed", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_reproduces_versioned_seed():
    # read_text normaliza CRLF: o checkout no Windows pode trocar o fim de linha.
    assert load_generator().build() == SEED_SQL.read_text(encoding="utf-8")


def test_seed_fits_large_file_hook():
    assert SEED_SQL.stat().st_size < 1024 * 1024


def test_seed_covers_every_table():
    sql = SEED_SQL.read_text(encoding="utf-8")
    tables = ("regioes", "categorias", "produtos", "vendedores", "clientes", "pedidos")
    for table in (*tables, "itens_pedido", "metas"):
        assert f"INSERT INTO {table} " in sql
