-- Views analíticas lidas pelas tools (SPEC-07 e SPEC-08).
-- Regras: sem parâmetro, sem now() (datas literais, para o replay não envelhecer),
-- só pedidos faturados, valores arredondados, no máximo 25 linhas por view.
-- "2026" é o período fechado de jan a set de 2026; o seed termina em 2026-09-30.

-- Base comum, não exposta à aplicação: receita e custo de cada item faturado.
CREATE VIEW base_itens_faturados AS
SELECT
    p.id AS pedido_id,
    p.data_pedido,
    p.cliente_id,
    p.vendedor_id,
    i.produto_id,
    i.quantidade,
    i.quantidade * i.preco_unitario * (1 - i.desconto) AS receita,
    i.quantidade * pr.custo AS custo
FROM pedidos p
JOIN itens_pedido i ON i.pedido_id = p.id
JOIN produtos pr ON pr.id = i.produto_id
WHERE p.status = 'faturado';

CREATE VIEW vw_vendas_mensal AS
WITH mensal AS (
    SELECT
        date_trunc('month', data_pedido)::date AS mes,
        sum(receita) AS receita,
        count(DISTINCT pedido_id) AS pedidos
    FROM base_itens_faturados
    GROUP BY 1
)
SELECT
    to_char(mes, 'YYYY-MM') AS mes,
    round(receita, 2) AS receita,
    pedidos,
    round(receita / pedidos, 2) AS ticket_medio,
    round(100 * (receita / lag(receita) OVER (ORDER BY mes) - 1), 1) AS variacao_pct
FROM mensal
ORDER BY mensal.mes;

CREATE VIEW vw_vendas_por_categoria AS
SELECT
    c.nome AS categoria,
    round(sum(b.receita), 2) AS receita,
    sum(b.quantidade) AS unidades,
    round(100 * (sum(b.receita) - sum(b.custo)) / sum(b.receita), 1) AS margem_pct,
    round(100 * sum(b.receita) / sum(sum(b.receita)) OVER (), 1) AS participacao_pct
FROM base_itens_faturados b
JOIN produtos pr ON pr.id = b.produto_id
JOIN categorias c ON c.id = pr.categoria_id
WHERE b.data_pedido BETWEEN DATE '2026-01-01' AND DATE '2026-09-30'
GROUP BY c.nome
ORDER BY sum(b.receita) DESC;

CREATE VIEW vw_top_produtos AS
SELECT
    pr.nome AS produto,
    c.nome AS categoria,
    sum(b.quantidade) AS unidades,
    round(sum(b.receita), 2) AS receita
FROM base_itens_faturados b
JOIN produtos pr ON pr.id = b.produto_id
JOIN categorias c ON c.id = pr.categoria_id
WHERE b.data_pedido BETWEEN DATE '2026-01-01' AND DATE '2026-09-30'
GROUP BY pr.nome, c.nome
ORDER BY sum(b.receita) DESC
LIMIT 10;

CREATE VIEW vw_vendas_por_vendedor AS
WITH vendas AS (
    SELECT vendedor_id, sum(receita) AS receita, count(DISTINCT pedido_id) AS pedidos
    FROM base_itens_faturados
    WHERE data_pedido BETWEEN DATE '2026-01-01' AND DATE '2026-09-30'
    GROUP BY vendedor_id
),
meta AS (
    SELECT vendedor_id, sum(valor_meta) AS meta
    FROM metas
    WHERE mes BETWEEN DATE '2026-01-01' AND DATE '2026-09-01'
    GROUP BY vendedor_id
)
SELECT
    v.nome AS vendedor,
    r.nome AS regiao,
    round(coalesce(s.receita, 0), 2) AS receita,
    coalesce(s.pedidos, 0) AS pedidos,
    round(m.meta, 2) AS meta,
    round(100 * coalesce(s.receita, 0) / m.meta, 1) AS atingimento_pct
FROM vendedores v
JOIN regioes r ON r.id = v.regiao_id
JOIN meta m ON m.vendedor_id = v.id
LEFT JOIN vendas s ON s.vendedor_id = v.id
ORDER BY coalesce(s.receita, 0) DESC;

CREATE VIEW vw_vendas_por_regiao AS
SELECT
    r.nome AS regiao,
    round(sum(b.receita), 2) AS receita,
    count(DISTINCT b.pedido_id) AS pedidos,
    count(DISTINCT b.cliente_id) AS clientes_ativos,
    round(100 * sum(b.receita) / sum(sum(b.receita)) OVER (), 1) AS participacao_pct
FROM base_itens_faturados b
JOIN clientes cl ON cl.id = b.cliente_id
JOIN regioes r ON r.id = cl.regiao_id
WHERE b.data_pedido BETWEEN DATE '2026-01-01' AND DATE '2026-09-30'
GROUP BY r.nome
ORDER BY sum(b.receita) DESC;

CREATE VIEW vw_top_clientes AS
SELECT
    cl.nome AS cliente,
    cl.segmento,
    r.nome AS regiao,
    count(DISTINCT b.pedido_id) AS pedidos,
    round(sum(b.receita), 2) AS receita,
    max(b.data_pedido) AS ultima_compra
FROM base_itens_faturados b
JOIN clientes cl ON cl.id = b.cliente_id
JOIN regioes r ON r.id = cl.regiao_id
WHERE b.data_pedido BETWEEN DATE '2026-01-01' AND DATE '2026-09-30'
GROUP BY cl.nome, cl.segmento, r.nome
ORDER BY sum(b.receita) DESC
LIMIT 10;

CREATE VIEW vw_kpis AS
WITH atual AS (
    SELECT
        sum(receita) AS receita,
        sum(custo) AS custo,
        count(DISTINCT pedido_id) AS pedidos,
        count(DISTINCT cliente_id) AS clientes
    FROM base_itens_faturados
    WHERE data_pedido BETWEEN DATE '2026-01-01' AND DATE '2026-09-30'
),
anterior AS (
    SELECT sum(receita) AS receita
    FROM base_itens_faturados
    WHERE data_pedido BETWEEN DATE '2025-01-01' AND DATE '2025-09-30'
),
meta AS (
    SELECT sum(valor_meta) AS meta
    FROM metas
    WHERE mes BETWEEN DATE '2026-01-01' AND DATE '2026-09-01'
),
status AS (
    SELECT
        count(*) FILTER (WHERE status = 'cancelado')::numeric AS cancelados,
        count(*)::numeric AS todos
    FROM pedidos
    WHERE data_pedido BETWEEN DATE '2026-01-01' AND DATE '2026-09-30'
)
SELECT indicador, valor, unidade
FROM atual, anterior, meta, status,
LATERAL (VALUES
    (1, 'Receita jan-set 2026', round(atual.receita, 2), 'BRL'),
    (2, 'Receita jan-set 2025', round(anterior.receita, 2), 'BRL'),
    (3, 'Crescimento da receita', round(100 * (atual.receita / anterior.receita - 1), 1), '%'),
    (4, 'Pedidos faturados', atual.pedidos::numeric, 'pedidos'),
    (5, 'Ticket médio', round(atual.receita / atual.pedidos, 2), 'BRL'),
    (6, 'Clientes ativos', atual.clientes::numeric, 'clientes'),
    (7, 'Atingimento da meta', round(100 * atual.receita / meta.meta, 1), '%'),
    (8, 'Taxa de cancelamento', round(100 * status.cancelados / status.todos, 1), '%'),
    (9, 'Margem bruta', round(100 * (atual.receita - atual.custo) / atual.receita, 1), '%')
) AS k (ordem, indicador, valor, unidade)
ORDER BY k.ordem;
