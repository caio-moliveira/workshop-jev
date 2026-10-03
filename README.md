# JEV Jornada

**Jev × LLM: a mesma decisão, dois modelos, uma régua só.**

Um agente de vendas em LangGraph onde cada decisão do fluxo (é seguro? qual consulta responde? a resposta é fiel aos dados?) pode ser tomada pelo [Jev](https://docs.typesafe.ai), um modelo de decisão da TypeSafe AI, ou por um LLM de fronteira da OpenAI ou da Anthropic. Os dois recebem exatamente a mesma entrada e as mesmas perguntas, e o projeto mede resposta, latência, tokens e custo lado a lado, para uma pergunta ou para um lote inteiro.

O projeto mede; a conclusão é de quem roda.

![Playground: a mesma pergunta passando pelo pipeline Jev e pelo pipeline LLM, lado a lado](docs/images/playground.png)

## Por que isso existe

Quem tem LLM em produção paga preço de geração de texto em decisões que cabem num `if`: rotear, classificar, bloquear, verificar. Essas chamadas são lentas, caras e devolvem texto que precisa de parsing. O Jev promete resolver exatamente isso: não gera texto, recebe um estado e perguntas tipadas e devolve valores com probabilidade calibrada, em dezenas de milissegundos. Mas as evidências disponíveis são do próprio fabricante.

Este repositório é um jeito simples de testar essa promessa com dados e um fluxo reais. Nasceu como exercício do workshop *Antes do modelo, a decisão* da comunidade Jornada de Dados e fica aqui como ferramenta: troque o golden set pelo seu caso e rode a mesma comparação.

## Como funciona

Uma pergunta sobre as vendas da empresa fictícia Mercado Jornada passa por seis etapas. Duas são código, uma é geração de texto e três são decisões. É nas decisões que Jev e LLM disputam.

![Fluxo: guardrail, triage, tool, reply, verify e act. Azul é decisão, cinza é código, laranja é geração](docs/images/pipeline.png)

| Etapa | Quem decide | O que faz |
|---|---|---|
| `guardrail` | **Jev, LLM ou ambos** | Três perguntas sim/não: é tentativa de manipulação? pede dado pessoal sensível? está fora do escopo de vendas? |
| `triage` | **Jev, LLM ou ambos** | Uma escolha entre oito opções: qual das sete consultas responde a pergunta, ou nenhuma |
| `tool` | código | Executa um `SELECT` na view escolhida. O nome da view vem do registro em código, nunca do modelo |
| `reply` | só LLM | Escreve a resposta em português, só com os dados que a consulta devolveu |
| `verify` | **Jev, LLM ou ambos** | Três perguntas sim/não: a resposta é fiel aos dados? responde à pergunta? inventa número? |
| `act` | código | Libera, manda para revisão humana ou bloqueia, pelos limiares de confiança |

Três regras tornam a comparação justa:

- **Uma definição, dois modelos.** A mesma `NodeSpec` (campos do estado, perguntas e critérios) alimenta os dois providers. Não existe prompt por modelo. A única exceção é o modo *system prompt por etapa*, para medir o Jev contra um LLM bem instruído, como se faz em produção.
- **Modo "ambos".** Os dois modelos rodam em paralelo na mesma etapa, com a mesma entrada. Só o primário segue no fluxo; os dois resultados vão para as métricas.
- **Nada estimado.** Tokens vêm da resposta da API, latência do relógio monotônico, preços de `backend/config/pricing.yaml` com data e fonte. Acurácia é acerto contra o rótulo do golden set.

### Os modelos

| Família | Modelos no catálogo |
|---|---|
| TypeSafe | Jev 1.13.0 |
| OpenAI | GPT-6 Sol, GPT-6 Luna, GPT-5.6 Sol, GPT-5.6 Terra, GPT-5.6 Luna |
| Anthropic | Claude Opus 5.5, Claude Sonnet 5.5, Claude Haiku 4.5 |

O LLM é escolhido num dropdown e pode ser trocado por etapa. Os preços ficam em [`backend/config/pricing.yaml`](backend/config/pricing.yaml).

## Comece em cinco minutos

Sem chave e sem banco. O modo padrão é `replay`: respostas gravadas dos modelos e das consultas, reproduzidas com a latência original.

Pré-requisitos: [uv](https://docs.astral.sh/uv/) (instala o Python 3.12 sozinho) e Node 22 ou superior.

```bash
git clone https://github.com/caio-moliveira/workshop-jev
cd workshop-jev

# terminal 1: backend em http://localhost:8000
cd backend && uv sync && uv run uvicorn app.main:app --reload

# terminal 2: frontend em http://localhost:5173
cd frontend && npm install && npm run dev
```

Abra http://localhost:5173, escolha uma pergunta e clique em **Perguntar**.

Para rodar sem o frontend:

```bash
cd backend && uv run python -m app.cli run --limit 3
```

## As três telas

**Playground.** Uma pergunta, dois pipelines. Cada etapa abre o detalhe: o que o modelo respondeu, com que confiança, ou os dados que a consulta devolveu. A visão *Fluxo único* mostra o modo "ambos" numa coluna só.

**Lote.** N perguntas do golden set de uma vez. Acerto da consulta, custo total e por mil perguntas, latência p95 e concordância entre os modelos, com gráficos, tabela por pergunta e exportação em CSV ou JSON.

![Lote: cards de Jev e LLM, gráficos de acerto, latência e custo por etapa, e tabela por pergunta](docs/images/lote.png)

**Configuração.** Por etapa, `LLM`, `Jev` ou `Ambos`, e qual é o primário. As instruções do LLM (as mesmas perguntas do Jev ou um system prompt por etapa). O modelo de LLM, com preço. Os limiares que decidem entre liberar, revisar e bloquear.

![Configuração: providers por etapa, instruções do LLM, modelo e limiares](docs/images/configuracao.png)

## Rodar com as APIs de verdade

O modo `live` chama o Jev, o LLM e o Postgres. Precisa de Docker e das chaves.

1. Copie `.env.example` para `.env` e preencha `TYPESAFE_API_KEY` ([console.typesafe.ai](https://console.typesafe.ai/keys)), `OPENAI_API_KEY` e `ANTHROPIC_API_KEY`. O Jev está em acesso antecipado.
2. Suba o banco de vendas. O seed roda sozinho na primeira subida.
   ```bash
   docker compose up -d --wait        # Postgres em localhost:5433
   ```
3. Suba o backend em modo live, ou troque o modo na tela de Configuração.
   ```bash
   cd backend
   PROVIDER_MODE=live uv run --env-file ../.env uvicorn app.main:app --reload
   ```

Para conferir só as chaves: `cd backend && uv run --env-file ../.env pytest -m live`.

### Os dados

Postgres 17 com a Mercado Jornada: regiões, categorias, produtos, vendedores, clientes, pedidos, itens e metas, de janeiro de 2025 a setembro de 2026. O seed é gerado com semente fixa. As sete consultas leem views pequenas, sem parâmetros, com um usuário que só lê as views:

| Consulta | View | O que responde |
|---|---|---|
| `vendas_mensal` | `vw_vendas_mensal` | receita, pedidos e ticket médio por mês |
| `vendas_por_categoria` | `vw_vendas_por_categoria` | receita, margem e participação por categoria |
| `top_produtos` | `vw_top_produtos` | os 10 produtos de maior receita |
| `vendas_por_vendedor` | `vw_vendas_por_vendedor` | receita, meta e atingimento por vendedor |
| `vendas_por_regiao` | `vw_vendas_por_regiao` | receita, pedidos e clientes por região |
| `top_clientes` | `vw_top_clientes` | os 10 maiores clientes |
| `kpis` | `vw_kpis` | indicadores gerais de 2026 |

## Use com o seu caso

A comparação não depende do domínio de vendas. Para medir com os seus dados:

1. **Golden set.** `data/golden_set.json` tem 80 perguntas rotuladas (60 de vendas, 20 adversariais). Cada uma traz a consulta esperada e os rótulos do guardrail. Troque pelas suas.
2. **Consultas.** As views ficam em `db/init/` e o registro de tools em `backend/app/tools.py`. A `description` de cada tool é o critério que Jev e LLM recebem na triagem.
3. **Perguntas.** As sete perguntas tipadas das três etapas de decisão estão em `backend/app/specs.py`. Edite as instruções e os critérios uma vez; os dois modelos recebem a mesma coisa.
4. **Gravação.** Com o banco e as chaves, grave o replay para que qualquer pessoa reproduza o resultado sem chave:
   ```bash
   cd backend
   PROVIDER_MODE=live uv run --env-file ../.env python -m app.cli record
   ```

## Estrutura

```
backend/        FastAPI + LangGraph: grafo, providers (Jev, LLM, replay), métricas, CLI
  app/specs.py  as perguntas tipadas das etapas de decisão
  app/tools.py  registro das consultas (tool → view)
  config/       graph.yaml (providers, catálogo, limiares) e pricing.yaml (preços)
  fixtures/     respostas gravadas para o modo replay
frontend/       React + Vite: Playground, Lote e Configuração
data/           golden set e o gerador do seed
db/init/        schema, seed e views do Postgres
docs/           PRD, SPECs e material do workshop
```

## Desenvolvimento

```bash
cd backend && uv run pytest                 # unitários e contrato em replay
cd backend && uv run pytest -m db           # com o banco no ar
cd frontend && npm run lint && npm run typecheck && npm run build && npm run test
pre-commit run --all-files                  # ruff, gitleaks e higiene, da raiz
```

Commits seguem Conventional Commits (`tipo(escopo): descrição`), validados pelo commitlint. Uma branch por SPEC, squash merge, PR sem teste não entra. O que implementar está em [`docs/specs/`](docs/specs/README.md); o quê e por quê, em [`docs/PRD.md`](docs/PRD.md); as regras para agentes de código, em [`CLAUDE.md`](CLAUDE.md).

## O workshop

*Antes do modelo, a decisão*: como preparar um projeto de IA e escolher onde um modelo de decisão entra. A apresentação está em [`aprensetacao.html`](aprensetacao.html) (abra no navegador; `F` para tela cheia, `N` para as notas) e o roteiro do apresentador em [`docs/workshop.md`](docs/workshop.md).

Por [Caio Machado de Oliveira](https://www.linkedin.com/in/caiomoliveira/), para a comunidade Jornada de Dados.
