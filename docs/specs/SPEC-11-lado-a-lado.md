Status: concluída

# SPEC-11: Jev × LLM lado a lado no Playground

## Objetivo

Mostrar no Playground duas execuções completas em paralelo, uma em que o Jev decide todas as etapas e outra em que o LLM decide, cada uma com suas etapas e sua resposta final.

## Cobre do PRD

Seção 10 (Playground). RF-05, RF-06 e RF-07, agora também de ponta a ponta.

## Interfaces

### API

`POST /runs` aceita `pipeline: "jev" | "llm"` opcional. Com ele, a execução usa `GraphConfig.for_pipeline(provider)`: todos os nodes de decisão com aquele provider e ele como primário. `/config` não muda. O `reply` continua só LLM.

### Replay

A resposta gravada (`reply` em `fixtures/replay/llm/<id>.json`) diz de qual tool é (`reply.tool`). Se a execução chegar ao `reply` com outra tool, `ReplayReplyWriter` levanta `ReplayMissError` em vez de reaproveitar um texto que cita outros dados. `record` grava `reply.tool`.

### Frontend

- `useRun()` (`src/lib/useRun.ts`): uma execução acompanhada pela tela; a visão lado a lado usa duas.
- `AnswerCard` (`src/components/AnswerCard.tsx`): resposta, ação, motivo, fonte, tempo somado e custo dos modelos (`runTotals`).
- Playground com a escolha de visão "Jev × LLM lado a lado" (padrão quando algum node está em `both`) e "Fluxo único" (o modo Ambos da SPEC-10).
- Lado a lado: duas colunas com cabeçalho do pipeline, linha do tempo compacta e resposta; as linhas das colunas ficam alinhadas (`grid-rows-subgrid`). Num pipeline de um provider só, o detalhe da decisão é "Ver resposta do modelo".

## Critérios de aceite

- [x] `pipeline: "jev"` roda todas as decisões com o Jev; `pipeline: "llm"`, com o LLM; `/config` não muda; pipeline inválido é 422.
- [x] Em replay, `q-045` libera no pipeline Jev (kpis, 86%) e vai para revisão no pipeline LLM (vendedor, 72%).
- [x] Resposta gravada para outra tool não é reaproveitada.
- [x] `runTotals` soma a latência das chamadas e da consulta e o custo dos modelos.
- [x] Linha do tempo com um provider só mostra "Ver resposta do modelo".
- [x] Lint, typecheck, build e testes verdes; verificado no navegador em replay e em 390 px.

## Fora

- Gravar o caminho do LLM quando ele diverge do Jev e segue até a resposta: hoje o painel mostra a falta de gravação. Entra no `record` se o apresentador precisar.
- Métricas de lote por pipeline: o Lote continua comparando etapa por etapa no modo Ambos.
