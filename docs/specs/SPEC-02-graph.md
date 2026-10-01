Status: aceita

# SPEC-02: Grafo

## Objetivo

Montar o pipeline de triagem em LangGraph, configurável por `graph.yaml`, executável por linha de comando em replay e capaz de gravar as fixtures.

## Cobre do PRD

Seções 5, 7.4, 7.5, 7.6, catálogo da 7.7, e o job de replay da 13.2. RF-01, RF-02, RF-04 (emissão dos eventos), RF-11.

## Interfaces

### `backend/config/graph.yaml`

```yaml
config_version: "1"
mode: replay                  # replay | live; PROVIDER_MODE no ambiente sobrescreve
primary: jev                  # jev | llm
llm_model: "openai:gpt-5.6-luna"
providers:                    # por node: llm | jev | both
  guardrail: both
  triage: both
  verify: both
llm_model_overrides: {}       # por node, opcional
thresholds:
  guardrail_block: 0.70
  triage_min_confidence: 0.80
  verify_min_policy: 0.80
  verify_max_overpromise: 0.30
catalog:                      # alimenta o dropdown; os nove modelos do PRD 7.7
  - { label: "GPT-5.6 Luna", provider: openai, model_id: gpt-5.6-luna }
```

`backend/app/config.py`: `GraphConfig` (pydantic) e `load_config() -> GraphConfig`. Validação: se o primário de um node não está entre os providers do node (ex.: `primary: jev` com `triage: llm`), o primário daquele node é o único provider que ele tem.

### `backend/app/graph.py`

```python
class TriageState(TypedDict): ...           # como no PRD 7.5

class Event(BaseModel):
    type: Literal["run.started", "node.started", "provider.finished", "node.finished", "run.finished"]
    run_id: str
    node: str | None = None
    data: dict = {}

EventSink = Callable[[Event], Awaitable[None]]

@dataclass
class Providers:                              # jev, llm, reply e llm_by_node (overrides)
    ...

def build_providers(config: GraphConfig, simulate_latency: bool = True) -> Providers: ...
async def run_ticket(
    ticket: Ticket, config: GraphConfig, emit: EventSink | None = None,
    providers: Providers | None = None, policy: str | None = None, simulate_latency: bool = True,
) -> RunResult: ...

class RunResult(BaseModel):
    run_id: str
    config_version: str
    mode: Literal["replay", "live"]
    ticket_id: str
    guardrail: dict | None
    triage: dict | None
    draft_reply: str | None
    verify: dict | None
    action: Literal["auto", "human", "blocked"]
    path: list[str]                         # nodes visitados, em ordem
    metrics: list[NodeMetric]               # ProviderResult + node + is_primary
    errors: list[str]
```

### Comportamento

- `guardrail`, `triage`, `verify`: o `decision_node` do PRD 7.4. Em `both`, os dois providers rodam com `asyncio.gather`; os dois resultados vão para `metrics`; só o primário entra no estado.
- `reply`: só LLM (`llm_model`), texto livre, recebe ticket, política e triagem. Em replay lê o campo `reply` da fixture de `llm/`. Latência, tokens e custo entram em `metrics` com `node="reply"`.
- `act`: código puro, decide `auto`, `human` ou `blocked`.
- Arestas, com os limiares de `graph.yaml`:

| De | Para | Regra |
|---|---|---|
| `guardrail` | fim, `blocked` | qualquer noul do guardrail ≥ `guardrail_block` |
| `triage` | `act`, `human` | `fila.confidence` < `triage_min_confidence` |
| `verify` | `act`, `human` | `segue_politica` < `verify_min_policy` ou `promete_fora` ≥ `verify_max_overpromise` |
| `verify` | `act`, `auto` | caso contrário |

- Resultado primário com `parse_ok=False` ou `values_in_schema=False`, ou exceção no provider primário: a execução vai para `human` e o motivo entra em `errors`. Falha do provider não primário só é registrada.
- `mode: replay` resolve `jev` e `llm` para `ReplayProvider(source=...)`. `mode: live` resolve para `JevProvider` e `LLMProvider`.
- O estado guarda do ticket só `id`, `text` e `channel`: os rótulos do golden set nunca chegam aos providers. O payload é o mesmo para os dois providers e leva `ticket_id` no topo, para o replay.
- `reply` fica em `app/providers/reply.py` (`LLMReplyWriter`, `ReplayReplyWriter`); sua métrica entra em `metrics` como um `ProviderResult` sem respostas, com o texto em `raw`.

### `backend/app/cli.py`

```
uv run python -m app.cli run --limit 3                # usa o mode do config; imprime um resumo por ticket
uv run python -m app.cli run --ticket tk-0042
uv run python -m app.cli record --limit 330           # mode live obrigatório; grava fixtures/replay/
```

`record` roda cada ticket com os nodes em `both` e escreve os arquivos de `jev/` e `llm/` no formato da SPEC-06. Sai com código diferente de zero se faltar chave. O fluxo gravado segue o primário: se o Jev bloquear um ticket que o LLM deixaria passar, o replay com `primary: llm` não tem o `triage` desse ticket e vai para `human` com o erro registrado.

Em replay, `run` só considera os tickets que têm gravação; `--ticket` sem gravação sai com erro. `run` sai com código diferente de zero se alguma execução registrou erro. A saída força UTF-8 (o console do Windows usa cp1252).

## Critérios de aceite

Testes com providers falsos, sem rede.

- [x] Ticket com `injection` ≥ 0,70: `action="blocked"`, `path == ["guardrail"]`, `triage` e `reply` não rodam.
- [x] `fila.confidence` 0,60: `action="human"`, `reply` não roda.
- [x] Caminho feliz: `path == ["guardrail", "triage", "reply", "verify", "act"]`, `action="auto"`.
- [x] `promete_fora` 0,40: `action="human"`.
- [x] Em `both`, com os dois providers discordando da fila, o caminho segue o primário e `metrics` tem os dois resultados do node.
- [x] Trocar `primary` de `jev` para `llm` muda o caminho no mesmo cenário.
- [x] Mudar um limiar em `GraphConfig` muda a decisão sem tocar no código.
- [x] Primário com `parse_ok=False`: `action="human"` e `errors` não vazio.
- [x] `emit` recebe os eventos na ordem `run.started`, depois por node `node.started`, um `provider.finished` por provider, `node.finished`, e por fim `run.finished`.
- [x] `PROVIDER_MODE=replay uv run python -m app.cli run --limit 3` termina com código 0 sem nenhuma chave no ambiente. Este comando substitui o placeholder do job `replay` da CI.
- [ ] **Pendente, precisa das chaves do apresentador:** fixtures reais dos 330 tickets gravadas com `record` e commitadas (`data(data): fixtures de replay`); as três escritas à mão na SPEC-06 são substituídas.

## Fora

- HTTP, SSE e persistência: SPEC-03.
- Execução de lote e concorrência: SPEC-05.
- Checkpointer do LangGraph, interrupts e revisão humana de verdade: `human` é só um rótulo de ação.
- Bifurcar o grafo por provider.
