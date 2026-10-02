# JEV Jornada

Agente de vendas em LangGraph: responde perguntas sobre os dados de vendas de uma empresa fictícia escolhendo uma tool que lê uma view analítica do Postgres. Cada node de decisão pode rodar com um LLM convencional, com o Jev, ou com os dois ao mesmo tempo. Um frontend React mostra cada etapa em tempo real e, lado a lado, o que cada modelo respondeu, quanto tempo levou, quantos tokens consumiu e quanto custou, para uma pergunta ou para um lote.

O projeto mede; a conclusão é de quem roda. Detalhes em [`docs/PRD.md`](docs/PRD.md) e [`docs/specs/`](docs/specs/README.md).

```
guardrail → triage → tool → reply → verify → act
 decisão    decisão  código  só LLM   decisão  código
            (qual tool) (lê a view)
```

## Pré-requisitos

- [uv](https://docs.astral.sh/uv/) (instala o Python 3.12 sozinho)
- Node 22 ou superior
- Docker, só para o modo live e para gravar o replay (o banco de vendas)

## Rodar sem nenhuma chave (modo replay)

O modo padrão é `replay`: respostas gravadas dos modelos e das tools, reproduzidas com a latência original. Não precisa de chave nem de banco.

```
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Em outro terminal:

```
cd frontend
npm install
npm run dev
```

Abra http://localhost:5173. O backend fica em http://127.0.0.1:8000.

Também dá para rodar pelo terminal, sem frontend:

```
cd backend
uv run python -m app.cli run --limit 3
```

## O banco de vendas

Postgres 17 em Docker com a empresa fictícia Mercado Jornada: 8 tabelas (regiões, categorias, produtos, vendedores, clientes, pedidos, itens, metas), jan/2025 a set/2026, e 7 views que as tools leem.

```
docker compose up -d --wait        # Postgres em localhost:5433, já com seed e views
docker compose down -v             # apaga o volume; a próxima subida refaz o seed
```

| Tool | View | O que responde |
|---|---|---|
| `vendas_mensal` | `vw_vendas_mensal` | receita, pedidos e ticket médio por mês |
| `vendas_por_categoria` | `vw_vendas_por_categoria` | receita, margem e participação por categoria |
| `top_produtos` | `vw_top_produtos` | os 10 produtos de maior receita |
| `vendas_por_vendedor` | `vw_vendas_por_vendedor` | receita, meta e atingimento por vendedor |
| `vendas_por_regiao` | `vw_vendas_por_regiao` | receita, pedidos e clientes por região |
| `top_clientes` | `vw_top_clientes` | os 10 maiores clientes |
| `kpis` | `vw_kpis` | indicadores gerais de 2026 |

A aplicação conecta com o usuário `jev_app`, que só lê as views. O seed é gerado por `data/scripts/generate_sales_seed.py` com semente fixa.

## Rodar com as APIs de verdade (modo live)

Suba o banco (`docker compose up -d --wait`), copie `.env.example` para `.env` e preencha as chaves. Depois:

```
cd backend
PROVIDER_MODE=live uv run --env-file ../.env uvicorn app.main:app --reload
```

Ou troque o modo na tela de Configuração. Para conferir só as chaves:

```
cd backend
uv run --env-file ../.env pytest -m live
```

## As três telas

- **Playground**: a pergunta e, em duas colunas, o pipeline Jev e o pipeline LLM rodando ao mesmo tempo, cada um com as seis etapas e a sua resposta final. Cada etapa abre o detalhe: o que o modelo respondeu ou os dados que a view devolveu. A visão "Fluxo único" mostra o modo Ambos, com Jev e LLM respondendo cada etapa com a mesma entrada.
- **Lote**: N perguntas do golden set, com acerto da consulta, latência, custo e concordância por provider, gráficos, tabela e exportação em CSV ou JSON.
- **Configuração**: por etapa, `LLM`, `Jev` ou `Ambos`; qual é o primário; o modelo de LLM, com preço; os limiares; a lista de tools.

## Antes do workshop (apresentador)

Três coisas que só quem tem as chaves faz:

1. **Preços da Anthropic**: preencher `backend/config/pricing.yaml` e conferir os da OpenAI. Enquanto estiverem `null`, rodar com Claude falha em vez de registrar custo zero.
2. **Gravar o replay das 80 perguntas**: hoje só 6 têm gravação (escritas à mão a partir dos dados reais do banco), então o lote em replay só roda essas 6. Com o banco no ar:
   ```
   docker compose up -d --wait
   cd backend
   PROVIDER_MODE=live uv run --env-file ../.env python -m app.cli record
   ```
   O `record` grava antes o resultado das tools (`app.cli snapshot`). Commitar `backend/fixtures/replay/` com um commit `data:`.
3. **Revisar o golden set**: `data/golden_set.json` tem 60 perguntas de vendas e 20 adversariais, escritas à mão. Vale ler as marcadas como `fronteira`, onde a escolha da tool é discutível.

## Contribuir

```
uv tool install pre-commit
pre-commit install
```

Commits seguem Conventional Commits (`tipo(escopo): descrição`, descrição em minúscula). As regras estão em `commitlint.config.cjs`. O fluxo de trabalho por SPEC está em [`docs/specs/README.md`](docs/specs/README.md), e as regras para agentes, em [`CLAUDE.md`](CLAUDE.md).

Testes:

```
cd backend && uv run pytest
cd backend && uv run pytest -m db          # com o banco no ar
cd frontend && npm run lint && npm run typecheck && npm run build && npm run test
```
