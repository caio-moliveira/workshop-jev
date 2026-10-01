# JEV Jornada

Pipeline de triagem de tickets de suporte em LangGraph, onde cada node de decisão pode rodar com um LLM convencional, com o Jev, ou com os dois ao mesmo tempo. Um frontend React mostra, lado a lado, o que cada modelo respondeu, quanto tempo levou, quantos tokens consumiu e quanto custou, para um ticket ou para um lote de centenas.

O projeto mede; a conclusão é de quem roda. Detalhes em [`docs/PRD.md`](docs/PRD.md) e [`docs/specs/`](docs/specs/README.md).

```
guardrail → triage → reply → verify → act
 decisão    decisão   só LLM   decisão   código
```

## Pré-requisitos

- [uv](https://docs.astral.sh/uv/) (instala o Python 3.12 sozinho)
- Node 22 ou superior

## Rodar sem nenhuma chave (modo replay)

O modo padrão é `replay`: respostas gravadas de execuções reais, reproduzidas com a latência original.

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

## Rodar com as APIs de verdade (modo live)

Copie `.env.example` para `.env` e preencha as chaves. Depois:

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

- **Configuração**: por node, `LLM`, `Jev` ou `Ambos`; qual é o primário; o modelo de LLM, com preço; os limiares de confiança.
- **Playground**: um ticket atravessando o grafo, com os cards dos dois providers lado a lado e as discordâncias destacadas.
- **Lote**: N tickets do golden set, com acurácia, latência, custo e concordância por provider, gráficos, tabela e exportação em CSV ou JSON.

## Antes do workshop (apresentador)

Três coisas que só quem tem as chaves faz:

1. **Preços da Anthropic**: preencher `backend/config/pricing.yaml` e conferir os da OpenAI. Enquanto estiverem `null`, rodar com Claude falha em vez de registrar custo zero.
2. **Gravar o replay dos 330 tickets**: hoje só 3 tickets têm gravação (escritas à mão para a CI), então o lote em replay só roda esses 3.
   ```
   cd backend
   PROVIDER_MODE=live uv run --env-file ../.env python -m app.cli record
   ```
   Commitar o resultado em `backend/fixtures/replay/` com um commit `data:`.
3. **Revisar o golden set**: `data/golden_set.json` foi gerado por LLM a partir de rótulos sorteados antes do texto (`data/scripts/generate_golden_set.py`). Vale ler os tickets `hard` e os 30 adversariais.

## Contribuir

```
uv tool install pre-commit
pre-commit install
```

Commits seguem Conventional Commits (`tipo(escopo): descrição`, descrição em minúscula). As regras estão em `commitlint.config.cjs`. O fluxo de trabalho por SPEC está em [`docs/specs/README.md`](docs/specs/README.md), e as regras para agentes, em [`CLAUDE.md`](CLAUDE.md).

Testes:

```
cd backend && uv run pytest
cd frontend && npm run lint && npm run typecheck && npm run build && npm run test
```
