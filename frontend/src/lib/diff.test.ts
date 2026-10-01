import { describe, expect, it } from 'vitest'

import { disagreements, disagrees } from './diff'
import type { Answer, NodeMetric } from './types'

const answer = (value: string | number, confidence: number | null = null): Answer => ({
  value,
  confidence,
  probabilities: null,
})

describe('disagrees', () => {
  it('choice diferente discorda', () => {
    expect(disagrees('choice', answer('financeiro'), answer('pedidos'))).toBe(true)
    expect(disagrees('choice', answer('financeiro'), answer('financeiro'))).toBe(false)
  })

  it('score com nível diferente discorda', () => {
    expect(disagrees('score', answer(2), answer(1))).toBe(true)
    expect(disagrees('score', answer(2), answer(2))).toBe(false)
  })

  it('noul discorda só quando os valores caem em lados opostos de 0,5', () => {
    expect(disagrees('noul', answer(0.45), answer(0.55))).toBe(true)
    expect(disagrees('noul', answer(0.7), answer(0.9))).toBe(false)
    expect(disagrees('noul', answer(0.1), answer(0.3))).toBe(false)
  })
})

const metric = (provider: 'jev' | 'llm', answers: Record<string, Answer>): NodeMetric => ({
  provider,
  model: provider,
  answers,
  latency_ms: 1,
  tokens_in: 1,
  tokens_out: 1,
  cost_usd: 0,
  parse_ok: true,
  values_in_schema: true,
  raw: {},
  node: 'triage',
  is_primary: provider === 'jev',
})

describe('disagreements', () => {
  it('lista as perguntas do node em que os dois providers discordam', () => {
    const jev = metric('jev', {
      fila: answer('financeiro'),
      urgencia: answer(2),
      pede_reembolso: answer(0.9),
      risco_churn: answer(0.1),
    })
    const llm = metric('llm', {
      fila: answer('pedidos'),
      urgencia: answer(2),
      pede_reembolso: answer(0.8),
      risco_churn: answer(0.6),
    })

    expect(disagreements('triage', [jev, llm])).toEqual(new Set(['fila', 'risco_churn']))
  })

  it('com um provider só não há discordância', () => {
    expect(disagreements('triage', [metric('jev', { fila: answer('financeiro') })])).toEqual(
      new Set(),
    )
  })
})
