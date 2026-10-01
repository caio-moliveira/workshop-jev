import type { DecisionNode, NodeName } from './types'

// Contrato das perguntas (docs/specs/README.md). Os nomes vêm do backend; aqui
// só ficam o tipo, para comparar respostas, e o rótulo em português da tela.

export type QuestionType = 'choice' | 'score' | 'noul'

export const QUESTIONS: Record<
  DecisionNode,
  { name: string; type: QuestionType; label: string }[]
> = {
  guardrail: [
    { name: 'injection', type: 'noul', label: 'Prompt injection' },
    { name: 'dado_sensivel', type: 'noul', label: 'Dado sensível' },
    { name: 'fora_escopo', type: 'noul', label: 'Fora do escopo' },
  ],
  triage: [
    { name: 'fila', type: 'choice', label: 'Fila' },
    { name: 'urgencia', type: 'score', label: 'Urgência' },
    { name: 'pede_reembolso', type: 'noul', label: 'Pede reembolso' },
    { name: 'risco_churn', type: 'noul', label: 'Risco de cancelamento' },
  ],
  verify: [
    { name: 'segue_politica', type: 'noul', label: 'Segue a política' },
    { name: 'responde_pedido', type: 'noul', label: 'Responde ao pedido' },
    { name: 'promete_fora', type: 'noul', label: 'Promete fora da política' },
  ],
}

export const URGENCY_LABELS = ['pode esperar', 'esta semana', 'hoje']

export const NODE_LABELS: Record<NodeName, string> = {
  guardrail: 'Guardrail',
  triage: 'Triagem',
  reply: 'Resposta',
  verify: 'Verificação',
  act: 'Ação',
}

export const DECISION_NODES: DecisionNode[] = ['guardrail', 'triage', 'verify']

export const isDecisionNode = (node: NodeName): node is DecisionNode =>
  (DECISION_NODES as string[]).includes(node)
