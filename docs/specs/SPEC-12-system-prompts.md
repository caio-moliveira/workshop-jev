Status: concluída (falta gravar o replay no modo native)

# SPEC-12: System prompt por etapa para o LLM

## Objetivo

Deixar escolher, na Configuração, se o LLM recebe as mesmas perguntas do Jev (teste controlado) ou um system prompt escrito para cada etapa (como em produção), com a mesma saída estruturada nos dois casos.

## Cobre do PRD

Seções 7.2 e 10 (Configuração). Abre uma exceção à regra "o mesmo NodeSpec alimenta os dois providers": no modo `native`, o LLM recebe um prompt próprio; o Jev continua recebendo o NodeSpec.

## Interfaces

- `graph.yaml` / `GraphConfig.llm_prompt_style: "spec" | "native"`, padrão `spec`. Muda por `PUT /config`.
- `backend/config/prompts/{guardrail,triage,verify}.md`: os system prompts. No da triagem, `{tools}` vira a lista de `TOOLS` (uma fonte só para as opções).
- `app/prompts.py`: `load_prompt(node)`, `load_prompts()`. `GET /prompts` devolve os três já renderizados.
- `LLMProvider(..., prompt_style)`. No modo `native`, as mensagens são o system prompt da etapa e o estado em JSON (sem `question_id`). O schema de saída (`build_schema`) é o mesmo nos dois modos; `raw.prompt_style` registra o modo.
- Replay: as gravações do LLM no modo `native` ficam em `fixtures/replay/llm-native/` (`llm_fixture_dir`). Sem gravação nesse modo, nenhuma pergunta aparece como gravada e a execução não reaproveita o modo `spec`.
- `app.cli record --llm-prompts native` grava nesse diretório.
- Frontend: cartão "Instruções do LLM" na Configuração, com os prompts para leitura; o card do LLM mostra "system prompt" quando a resposta veio do modo `native`; o Playground recarrega as perguntas gravadas quando o modo muda e avisa quando não há nenhuma.

## Critérios de aceite

- [x] No modo `native`, o LLM recebe o system prompt da etapa e só o estado; nenhuma instrução do NodeSpec vai no texto.
- [x] O modo `spec` fica como era.
- [x] A saída estruturada tem as mesmas perguntas nos dois modos.
- [x] O prompt da triagem lista todas as tools e `nenhuma`.
- [x] Replay no modo `native` sem gravação falha com `ReplayMissError`, não usa a gravação do modo `spec`.
- [x] `GET /prompts`; `PUT /config` com `llm_prompt_style` válido e inválido.
- [x] O card do LLM marca o modo `native`.
- [ ] **Pendente, precisa das chaves:** `record --llm-prompts native` das 80 perguntas.

## Fora

- Prompt próprio para o Jev: ele não usa prompt de texto.
- Editar os prompts pela interface: são arquivos versionados.
