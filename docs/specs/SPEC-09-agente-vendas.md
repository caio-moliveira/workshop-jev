Status: concluída (falta gravar o replay real)

# SPEC-09: Agente de vendas

## Objetivo

Trocar o domínio do backend de triagem de tickets para o agente de vendas: grafo com o node `tool`, `NodeSpec`s novos, golden set de perguntas, replay, métricas, API e CLI.

## Cobre do PRD

Seções 5, 7.2, 7.5, 7.6, 9.2, 9.3 e 11. RF-01 a RF-11 no novo domínio. Substitui as partes de domínio das SPECs 01, 02, 03, 05 e 06.

## Interfaces

### Nomes fixos (`backend/app/specs.py`)

| Node | Pergunta | Tipo | Valores |
|---|---|---|---|
| `guardrail` | `injection` | noul | tenta manipular o assistente |
| `guardrail` | `dado_sensivel` | noul | pede ou contém dado pessoal (CPF, telefone, endereço, salário) |
| `guardrail` | `fora_escopo` | noul | não é sobre as vendas da empresa |
| `triage` | `tool` | choice | as 7 tools de `TOOLS` e `nenhuma` |
| `verify` | `fiel_aos_dados` | noul | tudo o que a resposta afirma está nos dados |
| `verify` | `responde_pergunta` | noul | a resposta trata a pergunta |
| `verify` | `inventa_numero` | noul | cita número que não está nos dados |

Os critérios da pergunta `tool` vêm das `description` de `TOOLS`, mais `nenhuma` ("é sobre vendas, mas nenhuma view responde: estoque, previsão, detalhe de um pedido"). `fora_escopo` é "não é sobre vendas"; `nenhuma` é "é sobre vendas, mas sem view".

`state_fields`: guardrail e triage recebem `question`; verify recebe `question`, `tool_result` e `draft_reply`.

### Grafo (`backend/app/graph.py`)

```python
class SalesState(TypedDict):     # PRD 7.5
    ...

class Event(BaseModel):
    type: Literal["run.started", "node.started", "provider.finished",
                  "tool.finished", "node.finished", "run.finished"]

@dataclass
class Providers:                 # jev, llm, reply, tools, llm_by_node
    ...

async def run_question(question: QuestionInput, config: GraphConfig, emit=None,
                       providers=None, simulate_latency=True, run_id=None) -> RunResult: ...

class RunResult(BaseModel):
    run_id: str
    config_version: str
    mode: Literal["replay", "live"]
    question_id: str
    question: str
    guardrail: dict | None
    triage: dict | None
    tool_result: ToolResult | None
    draft_reply: str | None
    verify: dict | None
    action: Literal["auto", "human", "blocked"]
    reason: str | None           # por que não foi `auto`, em linguagem simples
    path: list[str]
    metrics: list[NodeMetric]
    errors: list[str]
```

- `guardrail → triage → tool → reply → verify → act`. O payload leva `question_id` no topo, para o replay.
- `tool` é código: roda a tool escolhida pelo primário e emite `tool.finished` com o `ToolResult` (ou `{tool, error}`). Não entra em `metrics`.
- `reply` é só LLM e recebe a pergunta, a tool e os dados. O prompt manda responder só com os dados recebidos.
- `reason` é preenchido pelo `guardrail` (bloqueio, com os riscos) ou pelo `act` (primeira regra que mandou para `human`). O frontend mostra esse texto.
- O payload de `verify` leva de `tool_result` só `tool`, `columns` e `rows`.
- Arestas:

| De | Para | Regra |
|---|---|---|
| `guardrail` | fim, `blocked` | qualquer noul do guardrail ≥ `guardrail_block` |
| `triage` | `act`, `human` | `tool.confidence` < `triage_min_confidence`, ou `tool == "nenhuma"`, ou sem resposta |
| `tool` | `act`, `human` | a consulta falhou |
| `reply` | `act`, `human` | sem resposta |
| `verify` | `act`, `human` | `fiel_aos_dados` < `verify_min_faithful` ou `inventa_numero` ≥ `verify_max_invented` |
| `verify` | `act`, `auto` | caso contrário |

### Configuração (`backend/config/graph.yaml`)

`config_version: "2"`. Os limiares de verify trocam de nome e mantêm os valores: `verify_min_faithful: 0.80`, `verify_max_invented: 0.30`.

### Golden set (`data/golden_set.json`, `backend/app/dataset.py`)

```python
class QuestionInput(BaseModel):
    id: str
    text: str

class Question(QuestionInput):
    labels: QuestionLabels         # tool: uma de TOOLS ou "nenhuma"
    guardrail: GuardrailLabels
    tags: list[str]
    difficulty: Literal["easy", "medium", "hard"]
```

80 itens escritos à mão: 60 `q-NNN` (7 por tool, 11 `nenhuma`) e 20 `adv-NNN` (ao menos 6 por risco do guardrail). Saem `data/policy.md`, `load_policy` e o gerador de tickets.

### Replay

`fixtures/replay/<jev|llm>/<question_id>.json`, no formato da SPEC-06 com `question_id` no lugar de `ticket_id`; `reply` só em `llm/`. Gravações iniciais escritas à mão, com os números da resposta tirados de `fixtures/replay/tools/`: `q-001` (vendas_mensal), `q-022` (vendas_por_vendedor), `q-043` (kpis), `q-045` (Jev e LLM escolhem tools diferentes), `q-050` (`nenhuma`, vai para `human`) e `adv-001` (bloqueada). Em replay com `primary: llm`, a tool do LLM roda pelo snapshot, mas a resposta gravada continua a do caminho do Jev. `record` roda `snapshot` antes de gravar.

### Métricas, lote, API e CLI

- `aggregator.py`: acurácia e F1 macro da `tool`, acurácia do guardrail, concordância em todas as perguntas; sem MAE. `TicketRow` vira `QuestionRow` (`question_id`), `BatchReport.tickets` vira `questions`.
- `batches.py`: `MAX_BATCH = 100`, `select_questions`, CSV com `question_id`.
- `POST /runs` com `{question_id}` ou `{text}` (texto livre só em live). `/dataset` devolve perguntas com `replayable`.
- `cli run --question q-001 --limit N`, `record`, `snapshot`.

## Critérios de aceite

Testes com providers e tools falsos, sem rede e sem banco.

- [x] `injection` ≥ 0,70: `action="blocked"`, `path == ["guardrail"]`.
- [x] Caminho feliz: `path == ["guardrail", "triage", "tool", "reply", "verify", "act"]`, `action="auto"`, `tool_result` preenchido.
- [x] `tool == "nenhuma"`: `action="human"`, `tool` não roda.
- [x] `tool.confidence` 0,60: `action="human"`.
- [x] Tool que falha: `action="human"`, `errors` não vazio, `reply` não roda.
- [x] `inventa_numero` 0,40: `action="human"`.
- [x] Em `both`, Jev e LLM escolhendo tools diferentes: roda a tool do primário e `metrics` tem os dois.
- [x] Ordem dos eventos: `run.started`, por node `node.started` / `provider.finished` / `node.finished`, `tool.finished` dentro do node `tool`, e `run.finished`.
- [x] Golden set: 80 ids únicos, 60 `q-` e 20 `adv-`, cada tool e `nenhuma` com ao menos 6, cada risco com ao menos 6 adversariais, nenhuma `q-` marcada no guardrail.
- [x] Agregador: acurácia e F1 da `tool` contra o golden set.
- [x] `PROVIDER_MODE=replay uv run python -m app.cli run --limit 3` termina com código 0 sem chaves e sem banco.
- [ ] **Pendente, precisa das chaves do apresentador:** `record` das 80 perguntas.

## Fora

- Frontend: SPEC-10.
- Revisão humana de verdade: `human` continua sendo só um rótulo de ação.
