Status: concluída; domínio e visual substituídos pela SPEC-10

# SPEC-04: Frontend, Configuração e Playground

## Objetivo

Deixar uma pessoa configurar o grafo e ver um ticket atravessá-lo, com os dois providers lado a lado.

## Cobre do PRD

Seção 10, telas 1 e 2. RF-01, RF-02, RF-03, RF-05, RF-06, RF-07.

## Interfaces

Consome só as rotas da SPEC-03. Interface em português.

### `frontend/src/lib/`

- `types.ts`: tipos espelhando `GraphConfig`, `Ticket`, `ProviderResult`, `Answer`, `Event` e `RunResult` do backend. Escritos à mão; sem geração de código.
- `api.ts`: `getConfig`, `putConfig`, `getPricing`, `getDataset`, `postRun`, `getRun`. URL base em `VITE_API_URL`, padrão `http://127.0.0.1:8000`. Não `localhost`: o navegador tenta IPv6 primeiro e cai em qualquer outro processo escutando em `[::1]:8000`, enquanto o uvicorn escuta em `127.0.0.1`.
- `questions.ts`: tipo e rótulo em português de cada pergunta, espelhando a tabela de `docs/specs/README.md`.
- `format.ts`: latência, tokens, custo, percentuais e preço em pt-BR.
- `sse.ts`: `subscribeRun(runId, onEvent): () => void`, sobre `EventSource` nativo; devolve a função de cancelar.
- `runState.ts`: `reduceRun(state, event): RunViewState`, função pura que transforma a sequência de eventos no estado da tela (status por node, resultados por provider, caminho, ação). É onde ficam os testes.

### Páginas e componentes

Navegação por três abas, sem roteador: Configuração, Playground, Lote (a terceira fica vazia até a SPEC-05).

| Arquivo | Papel |
|---|---|
| `pages/Config.tsx` | Seletor de modo (replay ou live, o toggle de fallback do PRD 14). Por node de decisão: seletor `LLM \| Jev \| Ambos`. Primário global. Dropdown de modelo agrupado por provedor com preço de entrada e saída ao lado. Quatro campos de limiar. Botão salvar (`PUT /config`). O badge do modo fica no cabeçalho. |
| `pages/Playground.tsx` | Área de texto, seletor de ticket do golden set (em replay, só os `replayable`), botão executar. Mostra o gabarito do ticket escolhido. Grafo, cards, rascunho do `reply`, ação final, erros. |
| `components/FlowGraph.tsx` | `@xyflow/react` com os cinco nodes em posições fixas. Cor por status: aguardando, rodando, concluído, pulado, bloqueado. Aresta tomada destacada. Clique seleciona o node. |
| `components/ProviderCard.tsx` | Um provider em um node: resposta e confiança por pergunta, barra de probabilidades quando houver, latência, tokens, custo, badges de `parse_ok` e `values_in_schema`, marca de primário. |
| `components/DiffBadge.tsx` | Marca a pergunta em que os dois providers discordam. |

Regra de discordância, em `lib/diff.ts`: choice e score discordam se o `value` é diferente; noul discorda se os dois valores caem em lados opostos de 0,5.

Em modo replay, a área de texto fica desabilitada com o aviso de que só tickets do golden set rodam.

## Critérios de aceite

- [x] `npm run lint`, `npm run typecheck` e `npm run build` passam.
- [x] Teste de `reduceRun` com a sequência de eventos de um caminho feliz: os cinco nodes terminam em "concluído" e a ação é `auto`.
- [x] Teste de `reduceRun` com ticket bloqueado: `guardrail` em "bloqueado", os demais em "pulado".
- [x] Teste de `diff`: fila diferente discorda; nouls 0,45 e 0,55 discordam; nouls 0,70 e 0,90 não.
- [x] Teste de componente: `ProviderCard` com `parse_ok=false` mostra o badge de falha.
- [x] Manual, com o backend em replay: escolher um ticket, executar, ver os nodes mudarem de cor em sequência, abrir `triage` e ver dois cards com a discordância destacada.
- [x] Manual: trocar `triage` para "Jev" na Configuração, salvar, executar de novo e ver um único card.
- [x] Manual: o dropdown mostra os nove modelos do catálogo com preço; os da Anthropic sem preço aparecem como "preço não informado", sem quebrar.

Os critérios manuais foram conferidos com Chromium headless (Playwright) contra o backend em replay: cores mudando durante a execução, dois cards com quatro discordâncias destacadas em `tk-0002`, um card só depois de trocar `triage` para Jev, console sem erros.

## Fora

- Tela de lote: SPEC-05.
- Override de modelo por node na interface: o backend aceita (`llm_model_overrides`), a tela fica só com o global nesta versão.
- Tabela de preços editável (RF-12): P1.
- Responsividade para celular, tema escuro, internacionalização.
- Testes end-to-end com navegador.
