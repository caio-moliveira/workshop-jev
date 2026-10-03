Status: concluída; domínio substituído pela SPEC-09 (NodeSpecs) e SPEC-08 (tools)

# SPEC-01: Providers

## Objetivo

Fazer o mesmo `NodeSpec` virar uma chamada ao Jev e uma chamada a um LLM, com medição idêntica nas duas.

## Cobre do PRD

Seções 7.2, 7.3, 7.7 e 9.1. Base de RF-01 e RF-02.

## Interfaces

### `backend/app/specs.py`

Os três `NodeSpec`s, com os nomes de pergunta da tabela em `docs/specs/README.md`:

```python
GUARDRAIL: NodeSpec   # state_fields: ["ticket"]
TRIAGE: NodeSpec      # state_fields: ["ticket", "policy"]
VERIFY: NodeSpec      # state_fields: ["ticket", "policy", "draft_reply"]
NODE_SPECS: dict[str, NodeSpec]
```

Instruções e critérios em português. É a única fonte das perguntas: nenhum provider tem prompt próprio.

### `backend/app/metrics/pricing.py`

```python
def load_pricing(path: Path = CONFIG_DIR / "pricing.yaml") -> Pricing: ...
def cost_usd(model: str, tokens_in: int, tokens_out: int, pricing: Pricing) -> float: ...
```

`backend/config/pricing.yaml`:

```yaml
reference_date: "2026-10-02"
source: "páginas de preços da OpenAI, Anthropic e TypeSafe"
models:               # US$ por 1M tokens
  gpt-5.6-luna: { input: 0.20, output: 1.20 }
  jev-1.13.0:   { input: 0.042, output: 0 }
  # ... os nove modelos do PRD 7.7
```

Modelo sem preço em `pricing.yaml` é erro explícito (`PricingMissingError`), não custo zero. Os modelos da Anthropic entram com `input: null, output: null` até alguém preencher na véspera (PRD 7.7): a chave existe para o catálogo, mas rodar com eles falha até haver preço. Preenchidos em 03/10/2026.

### `backend/app/providers/jev.py`

```python
class JevProvider:
    def __init__(self, pricing: Pricing, model: str = "jev-1.13.0", client: AsyncTypeSafeClient | None = None): ...
    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult: ...
```

Usa `AsyncTypeSafeClient.system_one(state=payload, questions={...}, model=...)` do `typesafe-sdk`. Mapeamento da resposta para `Answer`:

| Tipo | `value` | `confidence` | `probabilities` |
|---|---|---|---|
| choice | `answer.choice` | `answer.confidence` | `answer.probabilities` |
| score | nível mais provável (int) | `answer.confidence` | `answer.probabilities` |
| noul | `answer.noul` | `None` | `None` |

`tokens_in` e `tokens_out` vêm de `response.usage`. `parse_ok` e `values_in_schema` são sempre `True`.

### `backend/app/providers/llm.py`

```python
class LLMProvider:
    def __init__(self, model: str, pricing: Pricing, chat_model: BaseChatModel | None = None): ...
    async def decide(self, node: NodeSpec, payload: dict) -> ProviderResult: ...

def build_prompt(node: NodeSpec, payload: dict) -> list[BaseMessage]: ...
def build_schema(node: NodeSpec) -> type[BaseModel]: ...
```

- `model` no formato `"<provider>:<model_id>"`, instanciado com `init_chat_model`. `reasoning_effort` em `none` (OpenAI) e sem extended thinking (Anthropic).
- `build_schema` gera um modelo pydantic com um campo por pergunta, cada um com `value` e `confidence` (0 a 1). `choice` vira `str` livre no schema de saída, de propósito: é o que permite medir `values_in_schema`.
- Chamada com `with_structured_output(schema, include_raw=True)`, para ler `usage_metadata` da mensagem bruta.
- Resposta que não valida no schema: `parse_ok=False`, `answers={}`, sem exceção.
- `values_in_schema=False` se algum `choice` está fora das opções, algum `score` fora dos níveis ou algum `noul` fora de [0, 1].

### Nos dois providers

- `latency_ms` medido com `time.perf_counter()` em volta da chamada, só ela.
- `cost_usd` calculado por `cost_usd()`, nunca no provider.
- `raw` guarda a resposta bruta.
- Erro de rede ou de API propaga como exceção; quem trata é o grafo (SPEC-02).

## Critérios de aceite

Todos os testes usam cliente falso injetado pelo construtor; nenhum precisa de chave ou rede.

- [x] Para cada `NodeSpec`, o corpo enviado ao Jev contém exatamente as perguntas do spec, com os mesmos `instructions` e `criteria`.
- [x] Para cada `NodeSpec`, o prompt do LLM contém o texto de todas as `instructions` e de todos os critérios do spec (teste de que os dois providers saem da mesma fonte).
- [x] `JevProvider` mapeia choice, score e noul conforme a tabela, a partir de uma resposta falsa do SDK.
- [x] `LLMProvider` com resposta válida: `parse_ok=True`, tokens lidos de `usage_metadata`.
- [x] `LLMProvider` com JSON inválido: `parse_ok=False`, sem exceção.
- [x] `LLMProvider` com fila inventada (`"suporte"`): `parse_ok=True`, `values_in_schema=False`.
- [x] `cost_usd("gpt-5.6-luna", 1_000_000, 1_000_000, pricing) == 1.40`; modelo desconhecido levanta erro.
- [x] `pricing.yaml` tem `reference_date`, `source` e os nove modelos do PRD 7.7.
- [x] Teste marcado `@pytest.mark.live` (fora da CI) chama Jev e um LLM de verdade com um ticket, para o apresentador validar as chaves: `cd backend && uv run --env-file ../.env pytest -m live`.

## Fora

- Node `reply` (geração): SPEC-02.
- Escolha de provider por node, modo `both`, primário: SPEC-02.
- Edição de preços pela interface (RF-12): P1.
- Retry e tratamento de rate limit além do que os SDKs já fazem.
