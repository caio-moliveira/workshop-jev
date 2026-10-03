# Workshop: Antes do modelo, a decisão

Roteiro de quem apresenta. A apresentação está em [`aprensetacao.html`](../aprensetacao.html) na raiz: abra no navegador, setas para avançar, `F` para tela cheia, `N` para as notas do apresentador. O que o público precisa para acompanhar está no [README](../README.md).

## Antes do workshop

Três coisas que só quem tem as chaves faz.

1. **Preços.** Os da Anthropic foram preenchidos em 03/10/2026 em `backend/config/pricing.yaml`; conferir os da OpenAI no dia. Modelo com preço `null` falha em vez de registrar custo zero.
2. **Gravar o replay das 80 perguntas.** Hoje só 6 têm gravação (escritas à mão a partir dos dados reais do banco), então o lote em replay só roda essas 6. Com o banco no ar:
   ```bash
   docker compose up -d --wait
   cd backend
   PROVIDER_MODE=live uv run --env-file ../.env python -m app.cli record
   ```
   O `record` grava antes o resultado das tools (`app.cli snapshot`). Commitar `backend/fixtures/replay/` com um commit `data:`.
3. **Revisar o golden set.** `data/golden_set.json` tem 60 perguntas de vendas e 20 adversariais. Vale reler as marcadas como `fronteira`, onde a escolha da tool é discutível.

## Roteiro da demo

A pergunta do gancho é a q-029 do golden set: "Qual região vendeu mais este ano?".

1. `docs/PRD.md` e `docs/specs/` em dois minutos: o que existia antes da primeira linha de código.
2. `backend/app/specs.py`: as sete perguntas tipadas, escritas uma vez para os dois modelos.
3. Playground com a pergunta do gancho em modo "ambos", abrindo o detalhe de cada etapa.
4. Uma pergunta adversarial, para ver o guardrail bloquear.
5. Lote e dashboard. Ao voltar, resumir o que o dashboard mostrou em uma frase, sem arredondar a favor de ninguém.

Fechamento: de seis etapas, só uma precisa de um modelo que escreve. Duas são código. Três são decisões, e para essas agora existe um jeito de medir quem decide melhor.
