import { describe, expect, it } from 'vitest'

import {
  BLOCKED,
  HAPPY,
  RUN,
  THRESHOLDS,
  TRIAGE,
  VERIFY,
  answer,
  decision,
  replay,
  result,
  SAFE,
} from '../test/runs'
import { failRun } from './runState'
import { stepSummary } from './steps'
import type { RunEvent } from './types'

describe('stepSummary', () => {
  const happy = replay(HAPPY)

  it('etapas concluídas: frase, tom e tempos por provider', () => {
    expect(stepSummary('guardrail', happy, THRESHOLDS)).toMatchObject({
      tone: 'ok',
      text: 'Pergunta segura',
      timings: [
        { label: 'Jev', provider: 'jev', ms: 40 },
        { label: 'LLM', provider: 'llm', ms: 1200 },
      ],
    })
    expect(stepSummary('triage', happy, THRESHOLDS)).toMatchObject({
      tone: 'ok',
      text: 'Vendas por mês · confiança 94%',
    })
    expect(stepSummary('tool', happy, THRESHOLDS)).toEqual({
      tone: 'ok',
      text: '2 linhas de vw_vendas_mensal',
      timings: [{ label: 'SQL', ms: 12 }],
    })
    expect(stepSummary('verify', happy, THRESHOLDS).text).toBe(
      'Fiel aos dados 96% · número inventado 4%',
    )
    expect(stepSummary('act', happy, THRESHOLDS)).toMatchObject({
      tone: 'ok',
      text: 'Resposta liberada',
    })
  })

  it('bloqueio: guardrail bloqueado com o motivo e as demais puladas', () => {
    const blocked = replay(BLOCKED)

    expect(stepSummary('guardrail', blocked, THRESHOLDS)).toMatchObject({
      tone: 'blocked',
      text: expect.stringMatching(/manipular/),
    })
    expect(stepSummary('triage', blocked, THRESHOLDS)).toMatchObject({
      tone: 'skipped',
      text: 'Não executada',
    })
  })

  it('confiança baixa ou nenhuma consulta pedem atenção', () => {
    const low = replay([
      HAPPY[0],
      ...decision('guardrail', SAFE),
      ...decision('triage', { tool: answer('kpis', 0.6) }),
    ])
    const none = replay([
      HAPPY[0],
      ...decision('guardrail', SAFE),
      ...decision('triage', { tool: answer('nenhuma', 0.9) }),
    ])

    expect(stepSummary('triage', low, THRESHOLDS)).toMatchObject({ tone: 'warn' })
    expect(stepSummary('triage', none, THRESHOLDS)).toMatchObject({
      tone: 'warn',
      text: 'Nenhuma consulta responde a pergunta',
    })
  })

  it('verificação reprovada pede atenção e a ação mostra o motivo', () => {
    const verify = { ...VERIFY, inventa_numero: answer(0.4) }
    const events: RunEvent[] = [
      ...HAPPY.slice(0, -5),
      ...decision('verify', verify),
      {
        type: 'run.finished',
        run_id: RUN,
        node: null,
        data: result({
          verify,
          action: 'human',
          reason: 'a verificação apontou número que não está nos dados',
        }),
      },
    ]
    const state = replay(events)

    expect(stepSummary('verify', state, THRESHOLDS).tone).toBe('warn')
    expect(stepSummary('act', state, THRESHOLDS)).toEqual({
      tone: 'warn',
      text: 'Revisão humana: a verificação apontou número que não está nos dados',
      timings: [],
    })
  })

  it('consulta que falhou aparece como erro', () => {
    const state = replay([
      HAPPY[0],
      ...decision('guardrail', SAFE),
      ...decision('triage', TRIAGE),
      { type: 'node.started', run_id: RUN, node: 'tool', data: {} },
      {
        type: 'tool.finished',
        run_id: RUN,
        node: 'tool',
        data: { tool: 'vendas_mensal', error: 'banco fora' },
      },
      { type: 'node.finished', run_id: RUN, node: 'tool', data: { ok: false } },
    ])

    expect(stepSummary('tool', state, THRESHOLDS)).toMatchObject({
      tone: 'error',
      text: 'A consulta falhou',
    })
  })

  it('etapa rodando e etapas que nunca rodam depois de uma falha de conexão', () => {
    const running = replay(HAPPY.slice(0, 2))
    expect(stepSummary('guardrail', running, THRESHOLDS).tone).toBe('running')
    expect(stepSummary('triage', running, THRESHOLDS).tone).toBe('waiting')

    const failed = failRun(running, 'caiu')
    expect(stepSummary('triage', failed, THRESHOLDS).tone).toBe('skipped')
  })
})
