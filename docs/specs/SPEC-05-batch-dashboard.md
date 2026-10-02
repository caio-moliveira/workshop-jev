Status: concluída; domínio substituído pela SPEC-09 (backend) e SPEC-10 (frontend)

# SPEC-05: Lote e Dashboard

## Objetivo

Rodar centenas de tickets do golden set e mostrar, em uma tela, acurácia, latência, custo e concordância por node e por provider.

## Cobre do PRD

Seção 9.2, rotas `/batches/*` da seção 11, tela 3 da seção 10. RF-08, RF-09, RF-10.

## Interfaces

### Rotas

| Método | Rota | Corpo ou parâmetros | Resposta |
|---|---|---|---|
| GET | `/batches/estimate` | `n`, `tag` | `{"n": 100, "estimated_cost_usd": 0.14}`, antes de rodar |
| POST | `/batches` | `{"n": 100, "tag": null}` | `202 {"batch_id": "...", "n": 100, "estimated_cost_usd": 0.14}` |
| GET | `/batches/{batch_id}/events` | | SSE |
| GET | `/batches/{batch_id}/report` | | `BatchReport` |
| GET | `/batches/{batch_id}/export` | `format=csv\|json` | arquivo |

- `n` de 1 a 330 (fora disso, 422); padrão 100. Em replay, só entram os tickets com gravação, e `n` na resposta diz quantos vão rodar de fato.
- A estimativa é um teto: média de tokens das gravações, por node e provider, vezes os preços atuais, como se todo ticket passasse por todos os nodes. Fica `null` se falta preço de algum modelo ou não há gravação.
- Concorrência com `asyncio.Semaphore(5)`; o valor fica em `graph.yaml` (`batch_concurrency`).
- A configuração é copiada no início do lote: `PUT /config` durante a execução não afeta um lote em andamento.
- Eventos: `batch.started`, `batch.progress` (`done`, `total`, e o resumo do ticket que terminou), `batch.finished` (com o `BatchReport`).
- Um ticket que falha conta como erro no relatório e não derruba o lote.
- Cada execução do lote é salva pelo store da SPEC-03 com `batch_id`; o relatório é salvo em `runs/batches/<batch_id>.json`.

### `backend/app/metrics/aggregator.py`

```python
def aggregate(results: list[RunResult], tickets: list[Ticket], config: GraphConfig) -> BatchReport: ...

class BatchReport(BaseModel):
    batch_id: str
    config_version: str
    mode: Literal["replay", "live"]
    llm_model: str
    n: int
    errors: int
    by_provider: dict[str, ProviderSummary]     # "jev", "llm"
    by_node: dict[str, dict[str, NodeSummary]]  # node -> provider
    by_question: dict[str, dict[str, QuestionSummary]]
    agreement: dict[str, float]                 # por pergunta, só quando os dois rodaram
    tickets: list[TicketRow]
```

Métricas P0, com as definições do PRD 9.2:

| Onde | Métricas |
|---|---|
| `QuestionSummary` | acurácia (`fila`, `urgencia`, nouls com limiar 0,5), F1 macro (`fila`), erro absoluto médio (`urgencia`) |
| `NodeSummary` | latência p50 e p95 (interpolação linear), amostras de latência para o histograma, tokens, custo total, taxa de `parse_ok=False`, taxa de `values_in_schema=False` |
| `ProviderSummary` | acurácia média, custo total, custo por 1.000 tickets, p95; só nodes de decisão (o `reply` é sempre LLM e entra em `by_node`) |
| `agreement` | % de tickets com a mesma resposta, pela regra de discordância da SPEC-04 |
| `TicketRow` | id, tags, ação, resposta de cada provider por pergunta, rótulo, flags `disagrees`, `wrong` (o primário errou alguma pergunta com rótulo) e `has_error` (a execução registrou erro) |

As perguntas de `verify` não têm rótulo no golden set: entram em latência, custo e concordância, não em acurácia. Tickets que não chegaram a um node ficam fora do denominador daquele node.

Exportação: o JSON é o `BatchReport`. O CSV tem uma linha por ticket, provider e pergunta, com `batch_id`, `config_version`, `model`, valor, confiança, rótulo, acerto, latência, tokens e custo do node.

### Frontend

- `lib/api.ts` ganha `postBatch`, `getBatchReport`, `exportUrl`; `lib/sse.ts` ganha `subscribeBatch`.
- `pages/Batch.tsx`: campo N, filtro por tag, botão executar com o custo estimado, barra de progresso. Cards de resumo por provider (acurácia, custo total, p95, concordância). Tabela de tickets com os filtros "só discordâncias" e "só erros"; clicar numa linha abre o ticket no Playground. Botões de exportar CSV e JSON.
- `components/charts/` com recharts: histograma de latência por provider, custo por node, acurácia por pergunta.

## Critérios de aceite

- [x] Testes do `aggregate` com um conjunto pequeno montado à mão, conferindo valores exatos de acurácia, F1 macro, erro absoluto médio, p50, p95, custo por 1.000 tickets e concordância.
- [x] `aggregate` com um só provider devolve `agreement` vazio, sem erro.
- [x] Ticket bloqueado no guardrail não entra no denominador de `triage`.
- [x] `POST /batches` com `n=10` em replay: o SSE entrega dez `batch.progress` e um `batch.finished`; o relatório tem `n == 10`.
- [x] `n=1000` é rejeitado com 422.
- [x] Exportação em CSV abre com `csv.DictReader` e tem o número de linhas esperado; a em JSON valida como `BatchReport`. As duas trazem `config_version`.
- [x] Um lote de 100 tickets em replay, com latência simulada desligada, termina em menos de 10 segundos.
- [x] Manual: rodar 100 tickets pela tela, ver o progresso, os três gráficos, filtrar "só discordâncias" e abrir um ticket no Playground.
- [x] Manual: trocar o modelo, rodar de novo e comparar os dois relatórios exportados.

Os testes de lote usam fixtures descartáveis em diretório temporário (cópias da gravação do `tk-0001`), porque só três tickets têm gravação real até o apresentador rodar `app.cli record`. Os critérios manuais foram conferidos com Chromium headless contra um backend servindo fixtures descartáveis: estimativa, progresso, cards, os três gráficos, filtros, exportação CSV e abertura do ticket no Playground. Cores do Jev e do LLM validadas com o script da skill de dataviz (CVD ΔE 24,7).

## Fora

- Brier score, ECE, curva de calibração e automação por limiar (RF-13): P1. O `BatchReport` guarda confiança e rótulo por ticket, então entram depois sem refazer o lote.
- Histórico e comparação entre lotes na interface (RF-14), SQLite: P1.
- Cancelar um lote em andamento.
- Métricas parciais a cada evento: o progresso mostra a contagem, o relatório vem no fim.
