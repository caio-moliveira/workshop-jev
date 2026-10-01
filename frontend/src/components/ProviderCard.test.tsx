// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { NodeMetric } from '../lib/types'
import { ProviderCard } from './ProviderCard'

afterEach(cleanup)

const metric = (changes: Partial<NodeMetric> = {}): NodeMetric => ({
  provider: 'llm',
  model: 'gpt-5.6-luna',
  answers: {
    fila: { value: 'financeiro', confidence: 0.9, probabilities: null },
    urgencia: { value: 2, confidence: 0.8, probabilities: null },
    pede_reembolso: { value: 0.95, confidence: 0.9, probabilities: null },
    risco_churn: { value: 0.1, confidence: 0.85, probabilities: null },
  },
  latency_ms: 1530,
  tokens_in: 1190,
  tokens_out: 88,
  cost_usd: 0.000344,
  parse_ok: true,
  values_in_schema: true,
  raw: {},
  node: 'triage',
  is_primary: false,
  ...changes,
})

describe('ProviderCard', () => {
  it('mostra as respostas, a latência e o modelo', () => {
    render(<ProviderCard node="triage" outcome={metric()} disagreements={new Set()} />)

    expect(screen.getByText('financeiro')).toBeTruthy()
    expect(screen.getByText('hoje')).toBeTruthy()
    expect(screen.getByText('1,53 s')).toBeTruthy()
    expect(screen.getByText(/gpt-5.6-luna/)).toBeTruthy()
  })

  it('mostra o badge de falha quando o JSON não veio válido', () => {
    render(
      <ProviderCard
        node="triage"
        outcome={metric({ parse_ok: false, answers: {} })}
        disagreements={new Set()}
      />,
    )

    expect(screen.getByText('JSON inválido')).toBeTruthy()
  })

  it('mostra o badge quando o LLM inventou uma opção', () => {
    render(
      <ProviderCard
        node="triage"
        outcome={metric({ values_in_schema: false })}
        disagreements={new Set()}
      />,
    )

    expect(screen.getByText('valor fora das opções')).toBeTruthy()
  })

  it('destaca as perguntas com discordância', () => {
    render(<ProviderCard node="triage" outcome={metric()} disagreements={new Set(['fila'])} />)

    expect(screen.getByTestId('answer-fila').dataset.disagrees).toBe('true')
    expect(screen.getByTestId('answer-urgencia').dataset.disagrees).toBe('false')
  })

  it('mostra o erro quando o provider falhou', () => {
    render(
      <ProviderCard
        node="triage"
        outcome={{ provider: 'jev', is_primary: true, error: 'timeout' }}
        disagreements={new Set()}
      />,
    )

    expect(screen.getByText(/timeout/)).toBeTruthy()
  })
})
