Status: rascunho

# SPEC-06: Golden set e replay

## Objetivo

Entregar os dados rotulados e o modo de execução sem chaves, que são a base de teste de todas as outras SPECs.

## Cobre do PRD

Seções 7.2 e 7.3 (contratos), 9.3 (golden set), escopo P0 itens 6 e 7, RF-11.

## Interfaces

### Contratos, em `backend/app/providers/base.py`

`DecisionSpec`, `NodeSpec`, `Answer`, `ProviderResult` e o `Protocol` `DecisionProvider`, exatamente como no PRD 7.2 e 7.3. Ficam aqui, e não na SPEC-01, porque o `ReplayProvider` e as fixtures dependem deles.

Uma decisão desta SPEC sobre o PRD: o `ReplayProvider` devolve o `ProviderResult` gravado sem alterar `provider` nem `model` (`"jev"` ou `"llm"`). Assim métricas e telas tratam replay e real do mesmo jeito. O valor `"replay"` do `Literal` não é usado; quem diz que a execução foi replay é o campo `mode` da execução (SPEC-02).

### Golden set, em `data/`

- `data/golden_set.json`: lista de tickets no formato do PRD 9.3. 300 tickets de triagem (`tk-0001` a `tk-0300`) e 30 adversariais (`adv-001` a `adv-030`).
- `data/policy.md`: política de reembolso, curta (até uma página), usada no payload de `triage` e `verify`.
- `data/scripts/generate_golden_set.py`: gera os tickets por LLM a partir da taxonomia de 25 situações. Roda à mão, com chave. O resultado é revisado por uma pessoa antes do commit.
- `backend/app/dataset.py`:

```python
class Ticket(BaseModel):
    id: str
    text: str
    labels: TicketLabels          # fila, urgencia, pede_reembolso, risco_churn
    guardrail: GuardrailLabels    # injection, dado_sensivel, fora_escopo
    tags: list[str]
    difficulty: Literal["easy", "medium", "hard"]

def load_golden_set(tag: str | None = None, limit: int | None = None) -> list[Ticket]: ...
def load_policy() -> str: ...
```

### Fixtures, em `backend/fixtures/replay/`

Um arquivo por ticket e por provider: `fixtures/replay/<jev|llm>/<ticket_id>.json`.

```json
{
  "ticket_id": "tk-0042",
  "config_version": "1",
  "nodes": {
    "guardrail": { "...": "ProviderResult serializado" },
    "triage":    { "...": "ProviderResult serializado" },
    "verify":    { "...": "ProviderResult serializado" }
  },
  "reply": { "text": "...", "model": "...", "latency_ms": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0 }
}
```

- `reply` só existe no arquivo de `llm/`.
- Um node ausente significa que o fluxo gravado não passou por ele (ticket bloqueado no guardrail não tem `triage`).
- O replay cobre um único modelo de LLM, o que foi usado na gravação.

### `ReplayProvider`, em `backend/app/providers/replay.py`

```python
class ReplayProvider:
    def __init__(self, source: Literal["jev", "llm"], simulate_latency: bool = True): ...
    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult: ...

class ReplayMissError(Exception): ...   # ticket ou node sem fixture
```

`payload` carrega `ticket_id`. Com `simulate_latency=True` o provider dorme `latency_ms` antes de responder; os testes usam `False`.

## Critérios de aceite

- [ ] Teste valida o golden set: 330 itens, ids únicos, todo item passa no modelo `Ticket`, `fila` dentro das quatro opções, `urgencia` em 0..2.
- [ ] Teste de distribuição: cada fila tem pelo menos 40 tickets; cada nível de urgência pelo menos 60; os 30 adversariais cobrem os três riscos do guardrail (pelo menos 8 de cada).
- [ ] `load_golden_set(tag=..., limit=...)` filtra e limita; teste cobre os dois.
- [ ] `ReplayProvider.decide` devolve um `ProviderResult` igual ao gravado; levanta `ReplayMissError` com mensagem que cita ticket e node quando não há fixture.
- [ ] Com `simulate_latency=True`, a chamada demora pelo menos a latência gravada (teste com fixture de 50 ms).
- [ ] Existem fixtures de `jev/` e `llm/` para pelo menos três tickets (`tk-0001`, `tk-0002` e um adversarial), suficientes para o job de CI.
- [ ] Nenhum teste desta SPEC precisa de chave ou de rede.

## Fora

- Gravação das fixtures reais dos 330 tickets: precisa dos providers reais e do grafo, entra na SPEC-02. Até lá, as três fixtures são escritas à mão e trocadas pelas reais depois.
- Dados reais de clientes.
- Replay com mais de um modelo de LLM.
