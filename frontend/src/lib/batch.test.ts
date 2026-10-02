import { describe, expect, it } from 'vitest'

import {
  LATENCY_BINS,
  accuracyByQuestion,
  costByNode,
  filterRows,
  initialBatchState,
  latencyHistogram,
  reduceBatch,
} from './batch'
import type { BatchReport, NodeSummary, QuestionRow } from './types'

const node = (latencies: number[], cost = 0): NodeSummary => ({
  calls: latencies.length,
  latency_p50: null,
  latency_p95: null,
  tokens_in: 0,
  tokens_out: 0,
  cost_total: cost,
  parse_fail_rate: 0,
  out_of_schema_rate: 0,
  latencies,
})

const row = (id: string, flags: Partial<QuestionRow> = {}): QuestionRow => ({
  question_id: id,
  tags: [],
  action: 'auto',
  answers: {},
  labels: {},
  disagrees: false,
  wrong: false,
  has_error: false,
  ...flags,
})

const summary = (accuracy: number | null) => ({ n: 3, accuracy, f1_macro: null })

const report = (): BatchReport => ({
  batch_id: 'b1',
  config_version: '2',
  mode: 'replay',
  llm_model: 'openai:gpt-5.6-luna',
  primary: 'jev',
  n: 3,
  errors: 0,
  by_provider: {},
  by_node: {
    guardrail: { jev: node([40, 45], 0.001), llm: node([1200, 900], 0.02) },
    triage: { jev: node([60], 0.002), llm: node([1500], 0.03) },
    reply: { llm: node([3000], 0.05) },
  },
  by_question: {
    tool: { jev: summary(0.9), llm: summary(0.7) },
    fiel_aos_dados: { jev: summary(null) },
  },
  agreement: {},
  questions: [
    row('t1'),
    row('t2', { disagrees: true }),
    row('t3', { wrong: true, has_error: true }),
  ],
})

describe('reduceBatch', () => {
  it('acompanha o progresso e guarda o relatório no fim', () => {
    let state = reduceBatch(initialBatchState(), {
      type: 'batch.started',
      batch_id: 'b1',
      data: { n: 2 },
    })
    state = reduceBatch(state, {
      type: 'batch.progress',
      batch_id: 'b1',
      data: { done: 1, total: 2, question: { question_id: 't1', action: 'auto' } },
    })
    expect(state).toMatchObject({ status: 'running', done: 1, total: 2 })

    state = reduceBatch(state, { type: 'batch.finished', batch_id: 'b1', data: report() })
    expect(state.status).toBe('finished')
    expect(state.report?.batch_id).toBe('b1')
  })
})

describe('latencyHistogram', () => {
  it('conta as chamadas de decisão por faixa e por provider, sem o reply', () => {
    const bins = latencyHistogram(report())
    const bin = (label: string) => bins.find((b) => b.label === label)

    expect(bins.map((b) => b.label)).toEqual(LATENCY_BINS.map((b) => b.label))
    expect(bin('< 50 ms')).toMatchObject({ jev: 2, llm: 0 })
    expect(bin('50–100 ms')).toMatchObject({ jev: 1, llm: 0 })
    expect(bin('0,5–1 s')).toMatchObject({ jev: 0, llm: 1 })
    expect(bin('1–2 s')).toMatchObject({ jev: 0, llm: 2 })
    expect(bins.reduce((sum, b) => sum + b.llm, 0)).toBe(3)
  })
})

describe('costByNode', () => {
  it('soma o custo por node e provider, incluindo o reply', () => {
    expect(costByNode(report())).toEqual([
      { node: 'Guardrail', jev: 0.001, llm: 0.02 },
      { node: 'Triagem', jev: 0.002, llm: 0.03 },
      { node: 'Resposta', jev: 0, llm: 0.05 },
    ])
  })
})

describe('accuracyByQuestion', () => {
  it('só as perguntas com rótulo, em percentual', () => {
    expect(accuracyByQuestion(report())).toEqual([
      { question: 'Consulta escolhida', jev: 90, llm: 70 },
    ])
  })
})

describe('filterRows', () => {
  const rows = report().questions
  const ids = (filtered: QuestionRow[]) => filtered.map((r) => r.question_id)

  it('sem filtro devolve tudo', () => {
    expect(ids(filterRows(rows, 'all'))).toEqual(['t1', 't2', 't3'])
  })

  it('só discordâncias', () => {
    expect(ids(filterRows(rows, 'disagree'))).toEqual(['t2'])
  })

  it('só erros junta resposta errada e falha de execução', () => {
    expect(ids(filterRows(rows, 'errors'))).toEqual(['t3'])
  })
})
