# JEV Jornada

Pipeline de triagem de tickets de suporte em LangGraph, onde cada node de decisão roda com um LLM, com o Jev ou com os dois, e um frontend React compara resposta, latência, tokens e custo. É o exercício de um workshop e uma ferramenta reutilizável de medição.

O quê e por quê: `docs/PRD.md`. O que implementar: `docs/specs/` (comece pelo `README.md` de lá). Só implemente a partir de uma SPEC com status `aceita`.

## Como rodar

```
cd backend && uv sync && uv run uvicorn app.main:app --reload     # http://localhost:8000
cd frontend && npm install && npm run dev                          # http://localhost:5173
```

`PROVIDER_MODE=replay` é o padrão de desenvolvimento. Rode com chaves reais só quando a tarefa pedir.

## Como testar

```
cd backend && uv run pytest
cd backend && PROVIDER_MODE=replay uv run python -m app.cli run --limit 3   # contrato: sem chaves
pre-commit run --all-files                                         # da raiz: ruff, gitleaks, higiene
cd frontend && npm run lint && npm run typecheck && npm run build && npm run test
```

Toda SPEC concluída tem teste; PR sem teste não entra.

## Convenções

- Conventional Commits, validados pelo commitlint: `tipo(escopo): descrição`, descrição começando em minúscula. Tipos e escopos em `commitlint.config.cjs`.
- Uma branch por SPEC (`feat/spec-01-...`), squash merge, título do PR cita a SPEC.
- Nunca commit direto em `main`, nunca `git push --force`, nunca mover tags.
- Antes de codar uma SPEC, carregue as skills da tabela em `docs/specs/README.md`. Onde uma skill contradiz o PRD, o PRD vence (Python 3.12, React 18).

## Regras do domínio

- O mesmo `NodeSpec` alimenta os dois providers. Não crie prompts separados por provider.
- Em modo `both`, só o provider primário segue no fluxo; os dois vão para `metrics`.
- O node `reply` é só LLM.
- Preços vêm de `config/pricing.yaml`, nunca hardcoded.
- Tokens vêm da resposta da API e latência do relógio monotônico, nunca estimados.

## Não tocar sem pedir

`data/golden_set.json`, `backend/fixtures/replay/`, `backend/config/pricing.yaml` e os limiares em `backend/config/graph.yaml`. Mudanças neles alteram o resultado da comparação: exigem commit `data:` ou `config:` explícito e revisão humana.

## Segredos

Nunca leia, imprima ou commite valores do `.env`. Se encontrar uma chave em código, pare e avise.

## Definição de pronto

Lint limpo, testes passando, CI verde, modo replay funcionando, e este arquivo e a SPEC atualizados se as interfaces mudaram.
