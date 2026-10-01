Status: concluída

# SPEC-00: Passo 0, repositório e harness

## Objetivo

Deixar o repositório com as regras de trabalho, a CI e um scaffold que roda, para que as demais SPECs só adicionem código de produto.

## Cobre do PRD

Seção 13 inteira (13.1 a 13.5) e a estrutura da seção 12.

## Estado atual

Já feito:

- `.pre-commit-config.yaml` (higiene, ruff, gitleaks, commitlint), `commitlint.config.cjs`, `ruff.toml`, `.gitleaks.toml` (ignora os exemplos das skills de terceiros).
- `docs/PRD.md`, `docs/specs/README.md` e as SPECs em rascunho.
- Skills em `.claude/skills/` (com `skills-lock.json`) e plugins `python-master`, `react-master` e `tailwindcss-master` habilitados em `.claude/settings.json`.

Herdado de um experimento anterior e precisa ser limpo:

- `pyproject.toml`, `uv.lock` e `.python-version` na raiz (Python 3.13, dependências de um classificador de e-mails).
- `.env.example` com variáveis de IMAP; `.gitignore` com `classificacao_emails.csv`.
- `README.md` em UTF-16.
- `__pycache__/` na raiz.

## Interfaces

Arquivos que esta SPEC cria ou reescreve:

```
├── CLAUDE.md                       # as 8 seções do PRD 13.4
├── README.md                       # UTF-8: o que é, como rodar em replay, como rodar com chaves
├── .gitignore                      # .env, .venv/, node_modules/, __pycache__/, runs/, dist/
├── .env.example                    # TYPESAFE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, PROVIDER_MODE=replay
├── .claude/settings.json           # já tem os plugins; acrescentar permissões: uv, npm, pytest, ruff, git; negar git push --force e leitura de .env
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md    # o que muda, como testar, afeta replay?, afeta métricas ou preços?
│   └── workflows/ci.yml
├── backend/
│   ├── pyproject.toml              # Python 3.12, dependências com versão fixa (==)
│   ├── uv.lock
│   ├── app/__init__.py
│   ├── app/main.py                 # FastAPI com GET /health
│   └── tests/test_health.py
└── frontend/                       # Vite + React 18 + TypeScript + Tailwind, página vazia
    ├── .prettierrc                 # só o plugin prettier-plugin-tailwindcss
    └── package.json                # versões fixas; scripts dev, build, lint, typecheck, test, format
```

Comandos que passam a valer (e vão para o `CLAUDE.md`):

| O quê | Comando |
|---|---|
| Backend, instalar | `cd backend && uv sync` |
| Backend, rodar | `cd backend && uv run uvicorn app.main:app --reload` |
| Backend, testar | `cd backend && uv run pytest` |
| Lint e higiene | `pre-commit run --all-files` (da raiz; a versão do ruff é a fixada em `.pre-commit-config.yaml` e no `ci.yml`) |
| Frontend, instalar | `cd frontend && npm install` |
| Frontend, rodar | `cd frontend && npm run dev` |
| Frontend, checar | `cd frontend && npm run lint && npm run typecheck && npm run build` |

`GET /health` responde `200 {"status": "ok"}`.

Jobs do `ci.yml`, disparados por pull request:

- `backend`: `ruff check`, `ruff format --check`, `pytest`.
- `frontend`: `eslint`, `tsc --noEmit`, `vite build`.
- `replay`: placeholder que só passa. Vira o replay de três tickets na SPEC-02.

## Critérios de aceite

- [x] `pyproject.toml`, `uv.lock` e `.python-version` da raiz removidos; `backend/pyproject.toml` pede Python 3.12 e fixa `fastapi`, `uvicorn`, `langgraph`, `langchain`, `langchain-openai`, `langchain-anthropic`, `typesafe-sdk`, `pydantic`, `httpx`, `pyyaml`, e `pytest`, `pytest-asyncio` em dev.
- [x] `cd backend && uv sync && uv run pytest` passa, incluindo o teste do `/health`.
- [x] `cd frontend && npm install && npm run build` passa; `npm run dev` abre uma página.
- [x] `prettier` e `prettier-plugin-tailwindcss` em `devDependencies`; `npm run format` ordena as classes do Tailwind.
- [x] `.claude/settings.json` mantém `enabledPlugins` e `extraKnownMarketplaces` ao receber as permissões.
- [x] `pre-commit run --all-files` passa na árvore inteira.
- [x] `.env` não está rastreado; `.env.example` só tem as quatro variáveis, vazias (exceto `PROVIDER_MODE=replay`).
- [x] `CLAUDE.md` tem as oito seções do PRD 13.4 e cabe em uma tela e meia.
- [x] CI verde num PR (#1).
- [x] Commit final: `chore: passo 0, repositório e harness` (título do squash).

Configurado no GitHub (não verificável por teste): `main` protegida (PR obrigatório, os três jobs da CI obrigatórios, sem force push), squash merge como único método, secret scanning com push protection.

## Fora

- Qualquer código de produto (providers, grafo, rotas além de `/health`, telas).
- Tags `step-0` a `step-5`: criadas depois do ensaio.
- Renomear o repositório remoto (hoje `workshop-jev`, o PRD diz `jev-jornada`): decisão do dono do repositório.
- Hook de `pre-push` com testes e `actionlint`: a CI cobre.
