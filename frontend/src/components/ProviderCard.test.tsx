// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { NodeMetric } from '../lib/types'
import { ProviderCard } from './ProviderCard'

afterEach(cleanup)

const metric = (changes: Partial<NodeMetric> = {}): NodeMetric => ({
  provider: 'jev',
  model: 'jev-1.13.0',
  answers: {
    tool: {
      value: 'vendas_mensal',
      confidence: 0.94,
      probabilities: { vendas_mensal: 0.94, kpis: 0.04, top_produtos: 0.01, nenhuma: 0.01 },
    },
  },
  latency_ms: 1530,
  tokens_in: 536,
  tokens_out: 2,
  cost_usd: 0.0000225,
  parse_ok: true,
  values_in_schema: true,
  raw: {},
  node: 'triage',
  is_primary: true,
  ...changes,
})

describe('ProviderCard', () => {
  it('mostra a consulta escolhida pelo título, a confiança, a latência e o modelo', () => {
    render(<ProviderCard node="triage" outcome={metric()} disagreements={new Set()} />)

    expect(screen.getAllByText('Vendas por mês').length).toBeGreaterThan(0)
    expect(screen.getByText('confiança 94%')).toBeTruthy()
    expect(screen.getByText('1,53 s')).toBeTruthy()
    expect(screen.getByText('jev-1.13.0')).toBeTruthy()
    expect(screen.getByText('primário')).toBeTruthy()
  })

  it('mostra as três opções mais prováveis do Jev', () => {
    render(<ProviderCard node="triage" outcome={metric()} disagreements={new Set()} />)

    const options = screen.getByRole('list', { name: 'Probabilidade por opção' })
    expect(options.querySelectorAll('li')).toHaveLength(3)
    expect(screen.getByText('Indicadores gerais')).toBeTruthy()
  })

  it('noul aparece como percentual', () => {
    const verify = metric({
      node: 'verify',
      answers: {
        fiel_aos_dados: { value: 0.96, confidence: null, probabilities: null },
        responde_pergunta: { value: 0.97, confidence: null, probabilities: null },
        inventa_numero: { value: 0.04, confidence: null, probabilities: null },
      },
    })
    render(<ProviderCard node="verify" outcome={verify} disagreements={new Set()} />)

    expect(screen.getByText('96%')).toBeTruthy()
    expect(screen.getByText('4%')).toBeTruthy()
  })

  it('mostra o badge de falha quando o JSON não veio válido', () => {
    render(
      <ProviderCard
        node="triage"
        outcome={metric({ provider: 'llm', parse_ok: false, answers: {} })}
        disagreements={new Set()}
      />,
    )

    expect(screen.getByText('JSON inválido')).toBeTruthy()
    expect(screen.getByText('sem resposta')).toBeTruthy()
  })

  it('mostra o badge quando o LLM inventou uma opção', () => {
    render(
      <ProviderCard
        node="triage"
        outcome={metric({ provider: 'llm', values_in_schema: false })}
        disagreements={new Set()}
      />,
    )

    expect(screen.getByText('valor fora das opções')).toBeTruthy()
  })

  it('destaca as perguntas com discordância', () => {
    render(<ProviderCard node="triage" outcome={metric()} disagreements={new Set(['tool'])} />)

    expect(screen.getByTestId('answer-tool').dataset.disagrees).toBe('true')
    expect(screen.getByText('Jev e LLM discordam')).toBeTruthy()
  })

  it('marca quando o LLM respondeu com system prompt próprio', () => {
    render(
      <ProviderCard
        node="triage"
        outcome={metric({ provider: 'llm', raw: { prompt_style: 'native' } })}
        disagreements={new Set()}
      />,
    )

    expect(screen.getByText('system prompt')).toBeTruthy()
  })

  it('no modo spec não há a marca', () => {
    render(<ProviderCard node="triage" outcome={metric()} disagreements={new Set()} />)

    expect(screen.queryByText('system prompt')).toBeNull()
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
