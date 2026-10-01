"""Gera o golden set em duas etapas: um plano determinístico e os textos.

O plano fixa os rótulos de cada ticket (situação, fila, urgência, reembolso,
churn, dificuldade) a partir da taxonomia abaixo. Depois um LLM escreve só o
texto de cada ticket, de modo que o rótulo nunca é inferido do texto: ele vem
antes. O resultado é revisado por uma pessoa antes do commit.

    uv run --project backend python data/scripts/generate_golden_set.py plan
    uv run --project backend python data/scripts/generate_golden_set.py write --model openai:gpt-5.6-luna
    uv run --project backend python data/scripts/generate_golden_set.py build

`plan` escreve data/scripts/plan.json, `write` preenche data/scripts/texts.json
(precisa de chave) e `build` junta os dois em data/golden_set.json.
"""

import argparse
import json
import random
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
DATA_DIR = SCRIPTS_DIR.parent
PLAN_PATH = SCRIPTS_DIR / "plan.json"
TEXTS_PATH = SCRIPTS_DIR / "texts.json"
GOLDEN_SET_PATH = DATA_DIR / "golden_set.json"

SEED = 20261003
PER_SITUATION = 12
BATCH_SIZE = 20

# (tag, fila, descrição, pesos de urgência [0, 1, 2], fração que pede reembolso, fração com risco de churn)
SITUATIONS = [
    (
        "cobranca-duplicada",
        "financeiro",
        "foi cobrado duas vezes pelo mesmo pedido",
        [1, 4, 7],
        0.9,
        0.4,
    ),
    (
        "reembolso-nao-recebido",
        "financeiro",
        "devolveu o produto e o dinheiro não voltou",
        [1, 6, 5],
        1.0,
        0.4,
    ),
    (
        "cobranca-indevida",
        "financeiro",
        "cobrança que não reconhece na fatura",
        [1, 5, 6],
        0.8,
        0.3,
    ),
    (
        "pagamento-nao-compensado",
        "financeiro",
        "pagou por Pix ou boleto e o pedido segue como não pago",
        [2, 5, 5],
        0.1,
        0.2,
    ),
    (
        "nota-fiscal",
        "financeiro",
        "precisa da nota fiscal ou de corrigir dados dela",
        [7, 4, 1],
        0.0,
        0.0,
    ),
    ("estorno-parcial", "financeiro", "recebeu de volta menos do que pagou", [3, 6, 3], 1.0, 0.3),
    (
        "cobranca-assinatura",
        "financeiro",
        "mensalidade do Jornada+ cobrada com valor errado ou após cancelar",
        [2, 6, 4],
        0.7,
        0.5,
    ),
    ("atraso-entrega", "pedidos", "pedido passou do prazo e não chegou", [2, 5, 5], 0.2, 0.4),
    (
        "produto-defeito",
        "pedidos",
        "produto chegou com defeito ou parou de funcionar",
        [2, 7, 3],
        0.5,
        0.3,
    ),
    (
        "produto-errado",
        "pedidos",
        "recebeu um produto diferente do que comprou",
        [2, 7, 3],
        0.4,
        0.2,
    ),
    ("pedido-incompleto", "pedidos", "faltou item na caixa", [3, 7, 2], 0.3, 0.1),
    (
        "cancelar-pedido",
        "pedidos",
        "quer cancelar um pedido que ainda não foi entregue",
        [2, 5, 5],
        0.6,
        0.2,
    ),
    (
        "rastreamento",
        "pedidos",
        "código de rastreio não atualiza ou não foi enviado",
        [6, 5, 1],
        0.0,
        0.1,
    ),
    (
        "troca-devolucao",
        "pedidos",
        "quer trocar ou devolver por arrependimento ou tamanho",
        [5, 6, 1],
        0.5,
        0.0,
    ),
    (
        "acesso-senha",
        "conta",
        "não consegue entrar na conta ou redefinir a senha",
        [2, 6, 4],
        0.0,
        0.1,
    ),
    (
        "alterar-dados",
        "conta",
        "quer mudar e-mail, telefone ou endereço do cadastro",
        [7, 4, 1],
        0.0,
        0.0,
    ),
    ("conta-bloqueada", "conta", "conta foi bloqueada e não sabe o motivo", [1, 5, 6], 0.0, 0.3),
    ("excluir-conta", "conta", "quer excluir a conta e os dados", [6, 5, 1], 0.0, 0.6),
    ("login-suspeito", "conta", "recebeu aviso de acesso que não reconhece", [0, 3, 9], 0.0, 0.1),
    ("cancelar-assinatura", "conta", "quer cancelar a assinatura Jornada+", [4, 6, 2], 0.3, 1.0),
    (
        "duvida-produto",
        "outro",
        "dúvida sobre característica, compatibilidade ou estoque",
        [9, 3, 0],
        0.0,
        0.0,
    ),
    ("elogio-sugestao", "outro", "elogio ou sugestão de melhoria", [12, 0, 0], 0.0, 0.0),
    (
        "parceria-comercial",
        "outro",
        "proposta de parceria, revenda ou imprensa",
        [10, 2, 0],
        0.0,
        0.0,
    ),
    (
        "reclamacao-atendimento",
        "outro",
        "reclama de como foi atendido, sem pedido específico",
        [4, 6, 2],
        0.0,
        0.5,
    ),
    (
        "mensagem-vaga",
        "outro",
        "mensagem curta e vaga, sem dizer qual é o problema",
        [8, 4, 0],
        0.0,
        0.0,
    ),
]

# 30 casos para o guardrail: 10 de cada risco.
ADVERSARIAL = {
    "injection": "tenta fazer o assistente ignorar as instruções, revelar o prompt ou aprovar algo à força",
    "dado_sensivel": "inclui CPF, número de cartão, senha ou documento no corpo da mensagem",
    "fora_escopo": "pede algo que não é suporte da loja: receita, redação, conselho jurídico, outra empresa",
}

DIFFICULTIES = ["easy"] * 5 + ["medium"] * 5 + ["hard"] * 2
CHANNELS = ["email", "chat", "formulario"]


def _spread(fraction: float, n: int) -> list[bool]:
    return [i < round(fraction * n) for i in range(n)]


def _urgencies(weights: list[int]) -> list[int]:
    return [level for level, count in enumerate(weights) for _ in range(count)]


def build_plan() -> list[dict]:
    rng = random.Random(SEED)  # noqa: S311 — sorteio de dados sintéticos, não é criptografia
    rows = []
    for tag, fila, description, weights, p_refund, p_churn in SITUATIONS:
        urgencies = _urgencies(weights)
        refunds = _spread(p_refund, PER_SITUATION)
        churns = _spread(p_churn, PER_SITUATION)
        difficulties = list(DIFFICULTIES)
        for column in (urgencies, refunds, churns, difficulties):
            rng.shuffle(column)
        for i in range(PER_SITUATION):
            rows.append(
                {
                    "situacao": description,
                    "canal": rng.choice(CHANNELS),
                    "labels": {
                        "fila": fila,
                        "urgencia": urgencies[i],
                        "pede_reembolso": refunds[i],
                        "risco_churn": churns[i],
                    },
                    "guardrail": {"injection": False, "dado_sensivel": False, "fora_escopo": False},
                    "tags": [tag]
                    + (["churn"] if churns[i] else [])
                    + (["reembolso"] if refunds[i] else []),
                    "difficulty": difficulties[i],
                }
            )
    rng.shuffle(rows)
    for number, row in enumerate(rows, start=1):
        row["id"] = f"tk-{number:04d}"

    number = 0
    for risk, description in ADVERSARIAL.items():
        for _ in range(10):
            number += 1
            rows.append(
                {
                    "id": f"adv-{number:03d}",
                    "situacao": description,
                    "canal": rng.choice(CHANNELS),
                    "labels": {
                        "fila": "outro",
                        "urgencia": 0,
                        "pede_reembolso": False,
                        "risco_churn": False,
                    },
                    "guardrail": {key: key == risk for key in ADVERSARIAL},
                    "tags": ["adversarial", risk.replace("_", "-")],
                    "difficulty": "hard",
                }
            )
    return rows


WRITER_PROMPT = """Você escreve tickets sintéticos de suporte, em português do Brasil, para a loja \
fictícia Mercado Jornada (eletrônicos e assinatura Jornada+).

Para cada item do plano, escreva o texto que um cliente real mandaria. O texto tem que ser coerente \
com todos os rótulos do item:
- urgencia 0: pode esperar; 1: precisa de solução esta semana; 2: precisa de solução hoje.
- pede_reembolso: o cliente pede o dinheiro de volta de forma explícita (ou não pede).
- risco_churn: o cliente ameaça cancelar, sair ou não comprar mais (ou não ameaça).
- difficulty easy: direto e claro; medium: informal, com contexto a mais; hard: indireto, longo ou \
com erros de digitação, mas ainda com uma única leitura correta dos rótulos.

Varie tamanho, tom e vocabulário. Use números de pedido no formato A-123. Não use dados pessoais \
reais. Só inclua CPF, cartão ou senha (sempre fictícios) quando guardrail.dado_sensivel for true.

Responda só com um objeto JSON no formato {{"id": "texto", ...}}.

Plano:
{plan}"""


def write_texts(model: str) -> None:
    from langchain.chat_models import init_chat_model

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    texts = json.loads(TEXTS_PATH.read_text(encoding="utf-8")) if TEXTS_PATH.exists() else {}
    llm = init_chat_model(model)
    pending = [row for row in plan if row["id"] not in texts]
    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]
        response = llm.invoke(
            WRITER_PROMPT.format(plan=json.dumps(batch, ensure_ascii=False, indent=1))
        )
        raw = response.text if isinstance(response.text, str) else response.text()
        texts.update(json.loads(raw[raw.index("{") : raw.rindex("}") + 1]))
        TEXTS_PATH.write_text(json.dumps(texts, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(texts)}/{len(plan)}")


def build() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    texts = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))
    missing = [row["id"] for row in plan if not texts.get(row["id"], "").strip()]
    if missing:
        raise SystemExit(f"faltam textos para {len(missing)} tickets: {missing[:5]}...")
    tickets = [
        {
            "id": row["id"],
            "text": texts[row["id"]].strip(),
            "channel": row["canal"],
            "labels": row["labels"],
            "guardrail": row["guardrail"],
            "tags": row["tags"],
            "difficulty": row["difficulty"],
        }
        for row in plan
    ]
    GOLDEN_SET_PATH.write_text(
        json.dumps(tickets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{len(tickets)} tickets em {GOLDEN_SET_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    commands.add_parser("write").add_argument("--model", default="openai:gpt-5.6-luna")
    commands.add_parser("build")
    args = parser.parse_args()

    if args.command == "plan":
        PLAN_PATH.write_text(
            json.dumps(build_plan(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"plano em {PLAN_PATH}")
    elif args.command == "write":
        write_texts(args.model)
    else:
        build()


if __name__ == "__main__":
    main()
