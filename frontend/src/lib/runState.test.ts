import { describe, expect, it } from 'vitest'

import { initialRunState, reduceRun, takenEdges } from './runState'
import type { NodeMetric, NodeName, RunEvent, RunResult } from './types'

const RUN = 'r1'

const metric = (node: NodeName, provider: 'jev' | 'llm'): NodeMetric => ({
  provider,
  model: provider,
  answers: {},
  latency_ms: 10,
  tokens_in: 1,
  tokens_out: 1,
  cost_usd: 0,
  parse_ok: true,
  values_in_schema: true,
  raw: {},
  node,
  is_primary: provider === 'jev',
})

const result = (action: RunResult['action'], path: NodeName[]): RunResult => ({
  run_id: RUN,
  config_version: '1',
  mode: 'replay',
  ticket_id: 'tk-0001',
  guardrail: null,
  triage: null,
  draft_reply: action === 'auto' ? 'Seu estorno foi solicitado.' : null,
  verify: null,
  action,
  path,
  metrics: [],
  errors: [],
})

function nodeEvents(node: NodeName, providers: ('jev' | 'llm')[]): RunEvent[] {
  return [
    { type: 'node.started', run_id: RUN, node, data: {} },
    ...providers.map((p): RunEvent => ({
      type: 'provider.finished',
      run_id: RUN,
      node,
      data: metric(node, p),
    })),
    { type: 'node.finished', run_id: RUN, node, data: {} },
  ]
}

const replay = (events: RunEvent[]) => events.reduce(reduceRun, initialRunState())

describe('reduceRun', () => {
  it('caminho feliz: os cinco nodes concluídos e ação automática', () => {
    const path: NodeName[] = ['guardrail', 'triage', 'reply', 'verify', 'act']
    const state = replay([
      { type: 'run.started', run_id: RUN, node: null, data: {} },
      ...nodeEvents('guardrail', ['jev', 'llm']),
      ...nodeEvents('triage', ['jev', 'llm']),
      ...nodeEvents('reply', ['llm']),
      ...nodeEvents('verify', ['jev', 'llm']),
      ...nodeEvents('act', []),
      {
        type: 'run.finished',
        run_id: RUN,
        node: null,
        data: result('auto', path),
      },
    ])

    expect(state.status).toBe('finished')
    expect(Object.values(state.nodes)).toEqual(['done', 'done', 'done', 'done', 'done'])
    expect(state.action).toBe('auto')
    expect(state.path).toEqual(path)
    expect(state.outcomes.triage).toHaveLength(2)
    expect(state.draftReply).toBe('Seu estorno foi solicitado.')
  })

  it('ticket bloqueado: guardrail bloqueado e os demais pulados', () => {
    const state = replay([
      { type: 'run.started', run_id: RUN, node: null, data: {} },
      ...nodeEvents('guardrail', ['jev', 'llm']),
      {
        type: 'run.finished',
        run_id: RUN,
        node: null,
        data: result('blocked', ['guardrail']),
      },
    ])

    expect(state.nodes).toEqual({
      guardrail: 'blocked',
      triage: 'skipped',
      reply: 'skipped',
      verify: 'skipped',
      act: 'skipped',
    })
    expect(state.action).toBe('blocked')
  })

  it('node em andamento fica rodando e os resultados chegam um a um', () => {
    const state = replay([
      { type: 'run.started', run_id: RUN, node: null, data: {} },
      { type: 'node.started', run_id: RUN, node: 'guardrail', data: {} },
      {
        type: 'provider.finished',
        run_id: RUN,
        node: 'guardrail',
        data: metric('guardrail', 'jev'),
      },
    ])

    expect(state.status).toBe('running')
    expect(state.nodes.guardrail).toBe('running')
    expect(state.nodes.triage).toBe('waiting')
    expect(state.outcomes.guardrail.map((o) => o.provider)).toEqual(['jev'])
  })

  it('run.started de uma nova execução limpa a anterior', () => {
    const first = replay([
      { type: 'run.started', run_id: RUN, node: null, data: {} },
      ...nodeEvents('guardrail', ['jev']),
    ])

    const second = reduceRun(first, {
      type: 'run.started',
      run_id: 'r2',
      node: null,
      data: {},
    })

    expect(second.runId).toBe('r2')
    expect(second.outcomes.guardrail).toEqual([])
    expect(second.nodes.guardrail).toBe('waiting')
  })
})

describe('takenEdges', () => {
  it('liga os nodes consecutivos do caminho', () => {
    expect(takenEdges(['guardrail', 'triage', 'act'])).toEqual(['guardrail-triage', 'triage-act'])
  })
})
