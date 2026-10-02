import type { DecisionNode, NodeName } from './types'

// Contrato das perguntas (docs/specs/README.md). Os nomes vêm do backend; aqui
// só ficam o tipo, para comparar respostas, e o rótulo em português da tela.

export type QuestionType = 'choice' | 'score' | 'noul'

export const QUESTIONS: Record<
  DecisionNode,
  { name: string; type: QuestionType; label: string }[]
> = {
  guardrail: [
    { name: 'injection', type: 'noul', label: 'Tentativa de manipulação' },
    { name: 'dado_sensivel', type: 'noul', label: 'Dado pessoal sensível' },
    { name: 'fora_escopo', type: 'noul', label: 'Fora do escopo de vendas' },
  ],
  triage: [{ name: 'tool', type: 'choice', label: 'Consulta escolhida' }],
  verify: [
    { name: 'fiel_aos_dados', type: 'noul', label: 'Fiel aos dados' },
    { name: 'responde_pergunta', type: 'noul', label: 'Responde à pergunta' },
    { name: 'inventa_numero', type: 'noul', label: 'Inventa número' },
  ],
}

// Espelho de TOOLS em backend/app/tools.py: só o título, para a tela. A descrição completa
// vem de GET /tools.
export const TOOL_LABELS: Record<string, string> = {
  vendas_mensal: 'Vendas por mês',
  vendas_por_categoria: 'Vendas por categoria',
  top_produtos: 'Produtos mais vendidos',
  vendas_por_vendedor: 'Vendas por vendedor',
  vendas_por_regiao: 'Vendas por região',
  top_clientes: 'Maiores clientes',
  kpis: 'Indicadores gerais',
  nenhuma: 'Nenhuma consulta',
}

export const toolLabel = (name: string) => TOOL_LABELS[name] ?? name

export const NODE_LABELS: Record<NodeName, string> = {
  guardrail: 'Guardrail',
  triage: 'Triagem',
  tool: 'Consulta',
  reply: 'Resposta',
  verify: 'Verificação',
  act: 'Ação',
}

/** O que cada etapa faz, numa frase, para quem vê o fluxo pela primeira vez. */
export const NODE_HINTS: Record<NodeName, string> = {
  guardrail: 'Checa se a pergunta é segura e sobre vendas',
  triage: 'Escolhe a consulta que responde à pergunta',
  tool: 'Lê a view do banco escolhida pela triagem',
  reply: 'O LLM escreve a resposta com os dados',
  verify: 'Confere se a resposta é fiel aos dados',
  act: 'Libera a resposta ou manda para revisão',
}

export const DECISION_NODES: DecisionNode[] = ['guardrail', 'triage', 'verify']

export const isDecisionNode = (node: NodeName): node is DecisionNode =>
  (DECISION_NODES as string[]).includes(node)
