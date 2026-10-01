Status: rascunho

# SPEC-03: API e SSE

## Objetivo

Expor o grafo por HTTP: configurar, executar um ticket e acompanhar a execução em tempo real.

## Cobre do PRD

Seção 11 (rotas de config, pricing, dataset e runs) e o store da 7.1. RF-01 a RF-04, RF-11.

## Interfaces

### Rotas, em `backend/app/main.py`

| Método | Rota | Corpo ou parâmetros | Resposta |
|---|---|---|---|
| GET | `/health` | | `{"status": "ok"}` |
| GET | `/config` | | `GraphConfig` |
| PUT | `/config` | `GraphConfig` | `GraphConfig` validado; 422 se inválido |
| GET | `/pricing` | | conteúdo de `pricing.yaml` |
| GET | `/dataset` | `tag`, `limit` | lista de `Ticket` |
| POST | `/runs` | `{"ticket_id": "tk-0042"}` ou `{"text": "..."}` | `202 {"run_id": "..."}` |
| GET | `/runs/{run_id}/events` | | `text/event-stream` |
| GET | `/runs/{run_id}` | | `RunResult`; 404 se não existe; 409 se ainda rodando |

- `PUT /config` vale em memória, até o processo reiniciar. Não reescreve `graph.yaml`: limiares e providers versionados só mudam por commit `config:`.
- `POST /runs` com `text` cria um ticket sem rótulos, com id `adhoc-<run_id>`. Em modo replay, ticket digitado responde 422 com a mensagem "modo replay só executa tickets do golden set".
- `POST /runs` dispara a execução em uma task e retorna na hora.
- CORS liberado para `http://localhost:5173`.

### SSE

Cada evento do grafo (SPEC-02) vira uma mensagem:

```
event: provider.finished
data: {"type": "provider.finished", "run_id": "...", "node": "triage", "data": { ...ProviderResult, "is_primary": true }}
```

- `run.finished` carrega o `RunResult` completo em `data` e encerra o stream.
- Quem conecta depois do início recebe os eventos já emitidos e depois os novos. Quem conecta depois do fim recebe tudo e o stream fecha.
- Os eventos ficam em memória, por `run_id`, enquanto o processo vive.

### `backend/app/store.py`

```python
def save_run(result: RunResult) -> None: ...        # acrescenta uma linha em runs/runs.jsonl
def get_run(run_id: str) -> RunResult | None: ...
```

## Critérios de aceite

Testes com `httpx.AsyncClient` sobre o app, em modo replay, sem rede.

- [ ] `POST /runs` com um ticket do golden set devolve `run_id`; em seguida `GET /runs/{run_id}/events` entrega os eventos na ordem da SPEC-02 e fecha após `run.finished`.
- [ ] `GET /runs/{run_id}` depois do fim devolve o mesmo `RunResult` do evento `run.finished`.
- [ ] Conectar no SSE depois de a execução terminar ainda entrega todos os eventos.
- [ ] `PUT /config` trocando `triage` para `llm` muda o número de `provider.finished` do node na execução seguinte.
- [ ] `PUT /config` com limiar fora de [0, 1] ou provider desconhecido responde 422.
- [ ] `GET /dataset?tag=churn&limit=5` devolve no máximo cinco tickets, todos com a tag.
- [ ] `POST /runs` com `text` em modo replay responde 422.
- [ ] Cada execução concluída gera uma linha em `runs/runs.jsonl` com `config_version`.
- [ ] Subir o backend sem nenhuma chave no ambiente funciona em modo replay.

## Fora

- Rotas `/batches/*`: SPEC-05.
- `PUT /pricing` (RF-12) e histórico em SQLite (RF-14): P1.
- Autenticação e multiusuário.
- Reconexão de SSE com `Last-Event-ID`.
