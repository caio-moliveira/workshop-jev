# SPECs

O PRD (`docs/PRD.md`) diz o que o projeto é. Uma SPEC diz o que uma fatia dele entrega, com precisão suficiente para ser implementada e testada. O agente implementa a partir de uma SPEC aceita, nunca a partir do PRD direto.

## Ordem de implementação

| Ordem | SPEC | Entrega | Depende de |
|---|---|---|---|
| 0 | [SPEC-00](SPEC-00-passo-0.md) | Repositório, harness, CI e scaffold | nada |
| 1 | [SPEC-06](SPEC-06-golden-set-replay.md) | Golden set, contratos de provider, `ReplayProvider` | 00 |
| 2 | [SPEC-01](SPEC-01-providers.md) | `NodeSpec`s, `JevProvider`, `LLMProvider`, preços | 06 |
| 3 | [SPEC-02](SPEC-02-graph.md) | Grafo LangGraph, `graph.yaml`, CLI de replay e gravação | 01 |
| 4 | [SPEC-03](SPEC-03-api-sse.md) | API de um ticket, SSE, store JSONL | 02 |
| 5 | [SPEC-04](SPEC-04-frontend-config-playground.md) | Telas de Configuração e Playground | 03 |
| 6 | [SPEC-05](SPEC-05-batch-dashboard.md) | Lote, métricas agregadas, exportação, Dashboard | 03, 04 |

A SPEC-06 vem antes da 01 porque tudo o mais é testado contra o golden set e roda em replay.

## Formato

Toda SPEC tem as mesmas seções, nesta ordem:

1. **Objetivo**: uma frase.
2. **Cobre do PRD**: seções e requisitos (RF-xx).
3. **Interfaces**: assinaturas, rotas, schemas e arquivos que a SPEC expõe para as outras.
4. **Critérios de aceite**: cada um verificável por teste ou por um comando.
5. **Fora**: o que não entra, e onde entra (outra SPEC, P1 ou nunca).

## Ciclo de vida

O status fica na primeira linha da SPEC:

- `rascunho`: ainda em discussão. Não implementar.
- `aceita`: revisada por uma pessoa. Pode ser implementada.
- `concluída`: todos os critérios de aceite passam na `main`.

Uma SPEC vira uma ou mais branches (`feat/spec-01-jev-provider`). O título do PR referencia a SPEC: `feat(providers): JevProvider (SPEC-01)`. Se a implementação mudar uma interface, a SPEC e o `CLAUDE.md` são atualizados no mesmo PR.

## Nomes fixos entre as SPECs

Os nomes das perguntas são o contrato entre golden set, `NodeSpec`s, fixtures, métricas e frontend. Não renomear sem atualizar tudo.

| Node | Pergunta | Tipo | Valores |
|---|---|---|---|
| `guardrail` | `injection` | noul | probabilidade |
| `guardrail` | `dado_sensivel` | noul | probabilidade |
| `guardrail` | `fora_escopo` | noul | probabilidade |
| `triage` | `fila` | choice | `financeiro`, `pedidos`, `conta`, `outro` |
| `triage` | `urgencia` | score | `0` pode esperar, `1` esta semana, `2` hoje |
| `triage` | `pede_reembolso` | noul | probabilidade |
| `triage` | `risco_churn` | noul | probabilidade |
| `verify` | `segue_politica` | noul | probabilidade |
| `verify` | `responde_pedido` | noul | probabilidade |
| `verify` | `promete_fora` | noul | probabilidade |

## Skills e plugins por SPEC

Antes de escrever código de uma SPEC, carregar as skills da linha dela. As skills ficam em `.claude/skills/`; os plugins vêm do marketplace `josiahsiegel/claude-plugin-marketplace` e estão habilitados em `.claude/settings.json`.

| SPEC | Skills | Plugins |
|---|---|---|
| 00 | `fastapi`, `langchain-dependencies` (versões a fixar) | `python-master`, `react-master`, `tailwindcss-master` |
| 06 | `tdd` | `python-master` |
| 01 | `langchain-fundamentals`, `langchain-middleware` (structured output), `tdd` | `python-master` |
| 02 | `ecosystem-primer`, `langgraph-fundamentals`, `tdd` | `python-master` |
| 03 | `fastapi` (SSE), `tdd` | `python-master` |
| 04 | `tdd` | `react-master`, `tailwindcss-master` |
| 05 | `fastapi`, `tdd` | `python-master`, `react-master`, `tailwindcss-master` |

Onde uma skill ou plugin contradiz o PRD, o PRD vence:

- `python-master` assume Python 3.13+; o projeto é Python 3.12.
- `react-master` assume React 19 com Server Components; o projeto é React 18 com Vite, só componentes de cliente.
- `tailwindcss-master` assume Tailwind v4 (configuração em CSS, plugin `@tailwindcss/vite`); é a versão que o scaffold usa.
- `langgraph-persistence`, `langgraph-human-in-the-loop`, `langchain-rag`, `langfuse` e `shadcn` estão instaladas mas nenhuma SPEC as usa: sem checkpointer, sem interrupts, sem RAG, sem tracing, sem biblioteca de componentes.
