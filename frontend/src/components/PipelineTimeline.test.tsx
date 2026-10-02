// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { initialRunState } from '../lib/runState'
import { BLOCKED, HAPPY, THRESHOLDS, decision, replay, SAFE, answer } from '../test/runs'
import { PipelineTimeline } from './PipelineTimeline'

afterEach(cleanup)

const tones = () =>
  ['guardrail', 'triage', 'tool', 'reply', 'verify', 'act'].map(
    (node) => screen.getByTestId(`step-${node}`).dataset.tone,
  )

describe('PipelineTimeline', () => {
  it('antes de rodar mostra as seis etapas aguardando', () => {
    render(<PipelineTimeline run={initialRunState()} thresholds={THRESHOLDS} />)

    expect(screen.getAllByRole('listitem')).toHaveLength(6)
    expect(tones()).toEqual(Array(6).fill('waiting'))
  })

  it('caminho feliz: todas concluídas, com resumo, tempos e detalhes', () => {
    render(<PipelineTimeline run={replay(HAPPY)} thresholds={THRESHOLDS} />)

    expect(tones()).toEqual(Array(6).fill('ok'))
    const tool = screen.getByTestId('step-tool')
    expect(within(tool).getByText('2 linhas de vw_vendas_mensal')).toBeTruthy()
    expect(within(tool).getByText('Ver dados')).toBeTruthy()
    expect(within(screen.getByTestId('step-triage')).getByText('Comparar Jev × LLM')).toBeTruthy()
    expect(within(screen.getByTestId('step-guardrail')).getByText(/Jev 40 ms/)).toBeTruthy()
  })

  it('bloqueio no guardrail: as etapas seguintes aparecem como puladas', () => {
    render(<PipelineTimeline run={replay(BLOCKED)} thresholds={THRESHOLDS} />)

    expect(tones()).toEqual(['blocked', 'skipped', 'skipped', 'skipped', 'skipped', 'skipped'])
    expect(within(screen.getByTestId('step-triage')).queryByText('Comparar Jev × LLM')).toBeNull()
  })

  it('discordância entre Jev e LLM aparece na linha fechada', () => {
    const run = replay([
      HAPPY[0],
      ...decision('guardrail', SAFE),
      ...decision(
        'triage',
        { tool: answer('kpis', 0.86) },
        { tool: answer('vendas_por_vendedor', 0.72) },
      ),
    ])
    render(<PipelineTimeline run={run} thresholds={THRESHOLDS} />)

    expect(
      within(screen.getByTestId('step-triage')).getAllByText('Jev e LLM discordam').length,
    ).toBeGreaterThan(0)
    expect(
      within(screen.getByTestId('step-guardrail')).queryByText('Jev e LLM discordam'),
    ).toBeNull()
  })
})
