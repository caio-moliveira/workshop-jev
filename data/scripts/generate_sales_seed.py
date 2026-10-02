"""Gera db/init/02_seed.sql: os dados fictícios de vendas do Mercado Jornada (SPEC-07).

    uv run python ../data/scripts/generate_sales_seed.py     # de backend/

Determinístico: a mesma semente produz o mesmo arquivo, byte a byte. O SQL gerado é a
fonte da verdade e é versionado; o container não depende de Python. Regenerar muda os
números que as fixtures de replay citam: exige commit `data:` e revisão humana.
"""

import random
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SEED = 20261003
OUTPUT = Path(__file__).resolve().parents[2] / "db" / "init" / "02_seed.sql"

# Primeiro e último mês com dados: jan/2025 a set/2026.
MONTHS = [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 10)]
ORDERS_PER_MONTH_2025 = 110
GROWTH_2026 = 1.12
PRICE_INCREASE_2026 = Decimal("1.04")
SEASONALITY = {1: 0.85, 2: 0.85, 3: 0.95, 4: 0.95, 5: 1.0, 6: 0.95, 7: 0.95, 8: 1.0, 9: 1.0}
SEASONALITY |= {10: 1.05, 11: 1.3, 12: 1.4}
CANCEL_RATE = 0.05

# (nome, peso no volume de clientes)
REGIONS = [("Sudeste", 40), ("Sul", 18), ("Nordeste", 22), ("Centro-Oeste", 12), ("Norte", 8)]

# Categoria -> produtos (nome, preço de lista). A margem é da categoria.
CATALOG = {
    "Informática": (
        0.22,
        [
            ("Notebook Pro 14", 6899),
            ("Notebook Essencial 15", 3499),
            ('Monitor 27" 4K', 2299),
            ("Teclado Mecânico", 459),
            ("Mouse Sem Fio", 129),
            ("Dock USB-C", 899),
        ],
    ),
    "Eletrônicos": (
        0.25,
        [
            ("Smartphone X12", 3299),
            ("Tablet 11", 2499),
            ("Fone Bluetooth", 399),
            ("Caixa de Som Portátil", 549),
            ("Smartwatch Fit", 1199),
            ("Carregador Turbo", 149),
        ],
    ),
    "Eletrodomésticos": (
        0.28,
        [
            ("Cafeteira Expresso", 1299),
            ("Micro-ondas 30L", 899),
            ("Frigobar 120L", 1599),
            ("Purificador de Água", 749),
            ("Aspirador Vertical", 999),
            ("Ar-condicionado 12000", 2899),
        ],
    ),
    "Móveis de Escritório": (
        0.35,
        [
            ("Cadeira Ergonômica", 1890),
            ("Mesa Regulável", 2490),
            ("Gaveteiro Volante", 690),
            ("Armário Alto", 1350),
            ("Estação de Trabalho Dupla", 3990),
            ("Apoio de Pés", 189),
        ],
    ),
    "Papelaria": (
        0.42,
        [
            ("Resma A4 (caixa 10)", 289),
            ("Caneta Gel (caixa 50)", 119),
            ("Caderno Executivo", 59),
            ("Organizador de Mesa", 79),
            ("Etiqueta Adesiva (caixa)", 99),
            ("Quadro Branco 120x90", 459),
        ],
    ),
    "Limpeza e Copa": (
        0.38,
        [
            ("Kit Limpeza Profissional", 239),
            ("Papel Toalha (fardo)", 149),
            ("Café em Grãos 1kg", 89),
            ("Copo Biodegradável (caixa)", 69),
            ("Álcool Gel 5L", 99),
            ("Sabonete Líquido 5L", 79),
        ],
    ),
}
# Peso de cada categoria na escolha de itens.
CATEGORY_WEIGHTS = {
    "Informática": 18,
    "Eletrônicos": 15,
    "Eletrodomésticos": 10,
    "Móveis de Escritório": 12,
    "Papelaria": 25,
    "Limpeza e Copa": 20,
}

SELLERS = [
    ("Ana Ribeiro", "Sudeste"),
    ("Bruno Carvalho", "Sudeste"),
    ("Camila Duarte", "Sudeste"),
    ("Diego Martins", "Sudeste"),
    ("Eduarda Lima", "Sul"),
    ("Felipe Moraes", "Sul"),
    ("Gabriela Nunes", "Nordeste"),
    ("Henrique Sales", "Nordeste"),
    ("Isabela Rocha", "Nordeste"),
    ("João Teixeira", "Centro-Oeste"),
    ("Larissa Pacheco", "Centro-Oeste"),
    ("Marcos Vieira", "Norte"),
]

CLIENT_COUNT = 150
CLIENT_PREFIXES = [
    "Comercial", "Distribuidora", "Grupo", "Rede", "Atacado", "Mercado", "Escritório",
    "Clínica", "Colégio", "Construtora", "Hotel", "Indústria", "Farmácia", "Padaria",
    "Agência", "Transportadora",
]  # fmt: skip
CLIENT_NAMES = [
    "Aurora", "Horizonte", "Ipê", "Atlântico", "Serra Azul", "Bom Jesus", "Cerrado",
    "Pantanal", "Litoral", "Boa Vista", "Paraná", "Itaú", "Jacarandá", "Pioneiro",
    "Vale Verde", "Solar", "Estrela", "Primavera", "Central", "Planalto", "Tropical",
    "Nova Era", "Brasil Sul", "Alvorada", "Mirante",
]  # fmt: skip
CLIENT_SUFFIXES = ["Ltda", "S.A.", "ME", "EPP"]
# segmento: (peso, faixa de quantidade por item, propensão a comprar)
SEGMENTS = {
    "Varejo": (45, (1, 4), 1.0),
    "PME": (40, (2, 6), 1.4),
    "Corporativo": (15, (3, 10), 2.0),
}


def money(value: Decimal | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def insert(table: str, columns: list[str], rows: list[tuple], chunk: int = 500) -> str:
    """INSERT multi-linha, em blocos para não gerar um comando gigante."""
    parts = []
    for start in range(0, len(rows), chunk):
        values = ",\n".join(
            "(" + ", ".join(format_value(v) for v in row) + ")"
            for row in rows[start : start + chunk]
        )
        parts.append(f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n{values};\n")
    return "\n".join(parts)


def format_value(value) -> str:
    if isinstance(value, str):
        return sql_text(value)
    if isinstance(value, date):
        return f"'{value.isoformat()}'"
    return str(value)


def build() -> str:
    rng = random.Random(SEED)  # noqa: S311 — sorteio de dados sintéticos, não é criptografia

    regions = [(i, name) for i, (name, _) in enumerate(REGIONS, start=1)]
    region_id = {name: i for i, name in regions}

    categories, products = [], []
    for c_id, (category, (margin, items)) in enumerate(CATALOG.items(), start=1):
        categories.append((c_id, category))
        for name, price in items:
            cost = money(Decimal(price) * Decimal(str(1 - margin - rng.uniform(-0.04, 0.04))))
            products.append((len(products) + 1, c_id, name, money(price), cost))
    products_by_category = defaultdict(list)
    for product in products:
        products_by_category[product[1]].append(product)

    sellers = [(i, name, region_id[region]) for i, (name, region) in enumerate(SELLERS, start=1)]
    sellers_by_region = defaultdict(list)
    for s_id, _, r_id in sellers:
        sellers_by_region[r_id].append(s_id)

    # Lista, não set: a ordem de um set de strings muda a cada processo.
    names = [f"{p} {n}" for p in CLIENT_PREFIXES for n in CLIENT_NAMES]
    rng.shuffle(names)
    region_weights = [w for _, w in REGIONS]
    clients, client_weight = [], {}
    for c_id in range(1, CLIENT_COUNT + 1):
        segment = rng.choices(list(SEGMENTS), weights=[s[0] for s in SEGMENTS.values()])[0]
        r_id = rng.choices([i for i, _ in regions], weights=region_weights)[0]
        clients.append((c_id, f"{names[c_id - 1]} {rng.choice(CLIENT_SUFFIXES)}", segment, r_id))
        # Poucos clientes grandes concentram a receita, como na vida real.
        client_weight[c_id] = SEGMENTS[segment][2] * rng.paretovariate(3.5)
    segment_of = {c[0]: c[2] for c in clients}
    region_of = {c[0]: c[3] for c in clients}
    client_ids = [c[0] for c in clients]
    weights = [client_weight[c] for c in client_ids]

    category_ids = [c_id for c_id, _ in categories]
    category_weights = [CATEGORY_WEIGHTS[name] for _, name in categories]

    orders, items = [], []
    revenue = defaultdict(Decimal)  # (vendedor, ano, mês) -> receita faturada
    for year, month in MONTHS:
        growth = GROWTH_2026 if year == 2026 else 1.0
        count = round(ORDERS_PER_MONTH_2025 * growth * SEASONALITY[month] * rng.uniform(0.95, 1.05))
        days = (date(year + month // 12, month % 12 + 1, 1) - date(year, month, 1)).days
        for _ in range(count):
            o_id = len(orders) + 1
            c_id = rng.choices(client_ids, weights=weights)[0]
            s_id = rng.choice(sellers_by_region[region_of[c_id]])
            status = "cancelado" if rng.random() < CANCEL_RATE else "faturado"
            day = date(year, month, rng.randint(1, days))
            orders.append((o_id, c_id, s_id, day, status))

            low, high = SEGMENTS[segment_of[c_id]][1]
            n_items = rng.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
            for p_cat in rng.choices(category_ids, weights=category_weights, k=n_items):
                product = rng.choice(products_by_category[p_cat])
                quantity = rng.randint(low, high)
                if product[3] >= 1500:
                    # Item caro sai em quantidade menor; senão um pedido domina o mês.
                    quantity = max(1, quantity // 3)
                price = money(product[3] * (PRICE_INCREASE_2026 if year == 2026 else 1))
                discount = rng.choices(["0.00", "0.05", "0.10"], weights=[70, 22, 8])[0]
                items.append((len(items) + 1, o_id, product[0], quantity, price, discount))
                if status == "faturado":
                    revenue[(s_id, year, month)] += quantity * price * (1 - Decimal(discount))

    # Metas: cada vendedor tem um viés (uns batem, outros não) e ruído mensal, para o
    # atingimento ficar entre ~70% e ~130%.
    goals = []
    for s_id, _, _ in sellers:
        bias = rng.uniform(0.85, 1.15)
        for year, month in MONTHS:
            actual = revenue[(s_id, year, month)] or Decimal(20000)
            target = actual / Decimal(str(bias * rng.uniform(0.9, 1.1)))
            goals.append((s_id, date(year, month, 1), money(round(target, -3))))

    header = (
        "-- Gerado por data/scripts/generate_sales_seed.py (semente "
        f"{SEED}). Não editar à mão.\n"
        f"-- {len(clients)} clientes, {len(orders)} pedidos, {len(items)} itens.\n\n"
    )
    return header + "\n".join(
        [
            insert("regioes", ["id", "nome"], regions),
            insert("categorias", ["id", "nome"], categories),
            insert("produtos", ["id", "categoria_id", "nome", "preco_lista", "custo"], products),
            insert("vendedores", ["id", "nome", "regiao_id"], sellers),
            insert("clientes", ["id", "nome", "segmento", "regiao_id"], clients),
            insert("pedidos", ["id", "cliente_id", "vendedor_id", "data_pedido", "status"], orders),
            insert(
                "itens_pedido",
                ["id", "pedido_id", "produto_id", "quantidade", "preco_unitario", "desconto"],
                items,
            ),
            insert("metas", ["vendedor_id", "mes", "valor_meta"], goals),
        ]
    )


def main() -> None:
    OUTPUT.write_text(build(), encoding="utf-8", newline="\n")
    print(f"escrito {OUTPUT}")


if __name__ == "__main__":
    main()
