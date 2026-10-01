import { QUESTIONS, type QuestionType } from './questions'
import {
  isError,
  type Answer,
  type DecisionNode,
  type NodeMetric,
  type ProviderOutcome,
} from './types'

/** choice e score discordam se o valor muda; noul, se cai em lados opostos de 0,5. */
export function disagrees(type: QuestionType, a: Answer, b: Answer): boolean {
  if (type === 'noul') return Number(a.value) >= 0.5 !== Number(b.value) >= 0.5
  return a.value !== b.value
}

/** Perguntas do node em que os dois providers deram respostas diferentes. */
export function disagreements(node: DecisionNode, outcomes: ProviderOutcome[]): Set<string> {
  const metrics = outcomes.filter((o): o is NodeMetric => !isError(o))
  const result = new Set<string>()
  if (metrics.length < 2) return result
  const [a, b] = metrics
  for (const question of QUESTIONS[node]) {
    const left = a.answers[question.name]
    const right = b.answers[question.name]
    if (left && right && disagrees(question.type, left, right)) result.add(question.name)
  }
  return result
}
