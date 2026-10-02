Status: concluída

# SPEC-10: Frontend do agente de vendas

## Objetivo

Levar o frontend para o domínio de vendas e redesenhá-lo para que a pessoa entenda, sem explicação, o que o agente fez em cada etapa.

## Cobre do PRD

Seção 10. RF-03, RF-05, RF-06, RF-07, RF-09 no novo domínio. Substitui as partes de domínio e de visual das SPECs 04 e 05.

## Interfaces

### Domínio (`frontend/src/lib/`)

- `types.ts`: espelho de `QuestionInput`/`Question`, `Tool`, `ToolResult`, `RunResult`, `QuestionRow`, `BatchReport` e limiares da SPEC-09; `NodeName` inclui `'tool'`.
- `sse.ts`: assina `tool.finished`; erro de conexão encerra o run com mensagem, em vez de deixá-lo em "executando".
- `runState.ts`: node `tool`, campo `toolResult`, caso `tool.finished`.
- `questions.ts`: perguntas e rótulos novos; nomes das etapas.
- `steps.ts` (novo, puro): `stepSummary(node, run) -> { status, text, latencyMs }`, a frase de cada etapa ("Pergunta segura", "Tool: Vendas por mês · 93%", "21 linhas de vw_vendas_mensal · 12 ms", "Fiel aos dados 96%", "Resposta liberada").
- `api.ts`: `postRun({ question_id } | { text })`, `getTools()`.

### Visual

- Tailwind v4, tokens em `src/index.css` com `@theme`: superfícies, cor de marca, `ok`/`warn`/`danger`, e `jev`/`llm` com as cores atuais dos gráficos, para a cor seguir o provider em toda a tela. Sem dark mode.
- `src/components/ui/`: `Card`, `Button`, `Badge`, `Tabs` (tablist com setas do teclado e `aria-selected`), `DataTable`, `EmptyState`, `Skeleton`. Sem biblioteca de componentes.
- `@xyflow/react` e `FlowGraph.tsx` saem; entra `PipelineTimeline`.

### Playground

1. Campo da pergunta com rótulo e perguntas de exemplo do golden set (em replay, só as gravadas).
2. `PipelineTimeline`: uma linha por etapa com estado, frase de `stepSummary` e latência.
3. Detalhe sob demanda: cada etapa de decisão abre os `ProviderCard` de Jev e LLM; `DiffBadge` aparece na linha fechada quando há discordância; a etapa `tool` abre a `DataTable` dos dados.
4. Cartão da resposta com a ação e, quando não é liberada, o motivo em linguagem simples.
5. Estados vazio, carregando e erro; região `aria-live` com a etapa atual; foco visível; uma coluna no celular.

### Configuração e Lote

Textos do novo domínio, limiares renomeados, cartão "Tools disponíveis" (de `GET /tools`), acurácia da tool em destaque no Lote, componentes de `ui/`.

## Critérios de aceite

- [x] `npm run lint`, `npm run typecheck`, `npm run build` e `npm run test` verdes.
- [x] `reduceRun` trata `tool.finished` e guarda o `ToolResult`.
- [x] `stepSummary` cobre etapa concluída, pulada, bloqueada e com erro.
- [x] `PipelineTimeline` renderiza o caminho feliz e o bloqueio no guardrail (etapas seguintes como puladas).
- [x] `DataTable` mostra as colunas e as linhas do `ToolResult`.
- [x] Os testes existentes de `runState`, `diff`, `batch` e `ProviderCard` atualizados para o domínio novo.
- [x] Em replay, no navegador: `q-001` passa pelas seis etapas e mostra a tabela; `adv-001` para no guardrail.

## Fora

- Dark mode, router, biblioteca de componentes.
- Curva de calibração e automação por limiar: P1.
