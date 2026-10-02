Status: concluída

# SPEC-07: Banco de vendas

## Objetivo

Subir com um comando um Postgres em Docker com as tabelas, o seed determinístico e as views analíticas da empresa fictícia Mercado Jornada.

## Cobre do PRD

Seções 5.1, 7.1 (dados de vendas), 12 e 14. RF-15 (parte do banco).

## Interfaces

### `docker-compose.yml` (raiz)

- Serviço `db`, imagem `postgres:17`, porta `127.0.0.1:5433:5432` (5432 costuma estar ocupada por outros projetos).
- `POSTGRES_DB=vendas`, `POSTGRES_USER=postgres`, senha de desenvolvimento.
- Volume nomeado para os dados; `./db/init` montado em `/docker-entrypoint-initdb.d` somente leitura.
- Healthcheck `pg_isready -h 127.0.0.1 -U postgres -d vendas`, para `docker compose up -d --wait` só voltar com o init concluído.

### `db/init/`

Só arquivos `.sql`, executados em ordem alfabética na primeira subida (volume vazio):

| Arquivo | Conteúdo |
|---|---|
| `01_schema.sql` | `regioes`, `categorias`, `produtos`, `vendedores`, `clientes`, `pedidos`, `itens_pedido`, `metas`, com chaves estrangeiras |
| `02_seed.sql` | gerado por `data/scripts/generate_sales_seed.py`; nunca editado à mão |
| `03_views.sql` | as 7 views da tabela abaixo, sobre a view interna `base_itens_faturados` (receita e custo por item faturado), que a aplicação não lê |
| `04_roles.sql` | role `jev_app` com `SELECT` só nas views e `default_transaction_read_only = on` |

Views, todas sem parâmetro, sem `now()` (datas literais), só pedidos `faturado`, valores arredondados a 2 casas, no máximo 25 linhas:

| View | Colunas |
|---|---|
| `vw_vendas_mensal` | `mes`, `receita`, `pedidos`, `ticket_medio`, `variacao_pct` (jan/2025 a set/2026) |
| `vw_vendas_por_categoria` | `categoria`, `receita`, `unidades`, `margem_pct`, `participacao_pct` (2026) |
| `vw_top_produtos` | `produto`, `categoria`, `unidades`, `receita` (top 10 de 2026) |
| `vw_vendas_por_vendedor` | `vendedor`, `regiao`, `receita`, `pedidos`, `meta`, `atingimento_pct` (2026) |
| `vw_vendas_por_regiao` | `regiao`, `receita`, `pedidos`, `clientes_ativos`, `participacao_pct` (2026) |
| `vw_top_clientes` | `cliente`, `segmento`, `regiao`, `pedidos`, `receita`, `ultima_compra` (top 10 de 2026) |
| `vw_kpis` | `indicador`, `valor`, `unidade` (receita, receita do mesmo período de 2025, crescimento, pedidos, ticket médio, clientes ativos, atingimento de meta, cancelamento, margem bruta; 2026) |

### `data/scripts/generate_sales_seed.py`

```
uv run python ../data/scripts/generate_sales_seed.py     # reescreve db/init/02_seed.sql
```

`random.Random(20261003)`, sem dependência fora da biblioteca padrão. Dados coerentes: crescimento leve ano a ano, pico em novembro e dezembro, vendedor atende clientes da própria região, ~5% de pedidos cancelados, metas mensais que levam o atingimento a ficar entre ~70% e 130%. Nenhum dado pessoal: clientes são empresas fictícias.

## Critérios de aceite

- [x] `docker compose up -d --wait` sobe o banco com as 8 tabelas e as 7 views.
- [x] Rodar o gerador reproduz byte a byte o `02_seed.sql` versionado (teste sem banco, roda na CI).
- [x] `02_seed.sql` tem menos de 1024 KB (limite do pre-commit).
- [x] Com banco (marcador `db`, fora do `pytest` padrão): a receita de 2026 é a mesma somando `vw_vendas_por_categoria`, `vw_vendas_por_regiao`, os meses de 2026 de `vw_vendas_mensal` e o indicador de receita de `vw_kpis`.
- [x] Com banco: toda view tem no máximo 25 linhas.
- [x] Com banco: `jev_app` lê as views e não consegue ler `pedidos` nem escrever em nenhuma tabela.

## Fora

- Tools, driver e leitura pela aplicação: SPEC-08.
- Migrations, alembic e evolução de schema: o banco é recriado com `docker compose down -v`.
- Job de banco na CI: opcional, entra se sobrar tempo.
