"""Spec de teste com os três tipos de pergunta (choice, score e noul).

O domínio de vendas só usa choice e noul, mas os providers aceitam os três: estes testes
exercitam o mecanismo, não o domínio. É a triagem de tickets das SPECs 01 a 06.
"""

from app.providers.base import DecisionSpec, NodeSpec

TRIAGE = NodeSpec(
    name="triage",
    state_fields=["ticket", "policy"],
    questions=[
        DecisionSpec(
            name="fila",
            type="choice",
            instructions="Para qual fila de atendimento este ticket deve ir?",
            criteria={
                "financeiro": "Cobranças, estornos, reembolsos, pagamentos, nota fiscal.",
                "pedidos": "Entrega, atraso, defeito, produto errado, troca, cancelamento de pedido.",
                "conta": "Acesso, senha, cadastro, bloqueio, exclusão de conta, assinatura Jornada+.",
                "outro": "Dúvidas de produto, elogios, sugestões, parcerias e o que não couber acima.",
            },
        ),
        DecisionSpec(
            name="urgencia",
            type="score",
            instructions="Quão rápido o cliente precisa de uma solução?",
            criteria=[
                "Pode esperar.",
                "Precisa de solução esta semana.",
                "Precisa de solução hoje.",
            ],
        ),
        DecisionSpec(
            name="pede_reembolso",
            type="noul",
            instructions="O cliente pede o dinheiro de volta (reembolso ou estorno)?",
            criteria={
                "true": "Pede reembolso ou estorno de forma explícita.",
                "false": "Não pede dinheiro de volta.",
            },
        ),
        DecisionSpec(
            name="risco_churn",
            type="noul",
            instructions="O cliente ameaça cancelar, sair ou deixar de comprar na loja?",
            criteria={
                "true": "Há ameaça de cancelar, sair, ir para a concorrência ou não comprar mais.",
                "false": "Não há ameaça de abandono.",
            },
        ),
    ],
)
