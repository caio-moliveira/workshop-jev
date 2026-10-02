-- Usuário da aplicação: só lê as views das tools, nunca as tabelas, nunca escreve.
-- Senha de desenvolvimento: o banco só escuta em 127.0.0.1 (docker-compose.yml).

CREATE ROLE jev_app LOGIN PASSWORD 'jev_app';
ALTER ROLE jev_app SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE vendas TO jev_app;
GRANT USAGE ON SCHEMA public TO jev_app;
GRANT SELECT ON
    vw_vendas_mensal,
    vw_vendas_por_categoria,
    vw_top_produtos,
    vw_vendas_por_vendedor,
    vw_vendas_por_regiao,
    vw_top_clientes,
    vw_kpis
TO jev_app;
