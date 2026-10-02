import { describe, expect, it } from 'vitest'

import { BLOCKED, HAPPY, RUN, TOOL, decision, replay, SAFE } from '../test/runs'
import { currentNode, failRun, initialRunState, reduceRun } from './runState'

describe('reduceRun', () => {
  it('caminho feliz: as seis etapas concluídas e a resposta liberada', () => {
    const state = replay(HAPPY)

    expect(state.status).toBe('finished')
    expect(Object.values(state.nodes)).toEqual(['done', 'done', 'done', 'done', 'done', 'done'])
    expect(state.action).toBe('auto')
    expect(state.path).toEqual(['guardrail', 'triage', 'tool', 'reply', 'verify', 'act'])
    expect(state.outcomes.triage).toHaveLength(2)
    expect(state.draftReply).toBe('Em setembro a receita foi de R$ 578.064,86.')
    expect(state.question).toBe('Como foi a receita mês a mês em 2026?')
  })

  it('tool.finished guarda o resultado da consulta', () => {
    const toolDone = HAPPY.findIndex((e) => e.type === 'tool.finished') + 1
    const state = replay(HAPPY.slice(0, toolDone))

    expect(state.tool).toEqual(TOOL)
    expect(state.nodes.tool).toBe('running')
  })

  it('node.finished de decisão guarda as respostas do primário', () => {
    const state = replay(HAPPY.slice(0, 5))

    expect(state.answers.guardrail).toEqual(SAFE)
  })

  it('pergunta bloqueada: guardrail bloqueado, demais puladas e o motivo', () => {
    const state = replay(BLOCKED)

    expect(state.nodes).toEqual({
      guardrail: 'blocked',
      triage: 'skipped',
      tool: 'skipped',
      reply: 'skipped',
      verify: 'skipped',
      act: 'skipped',
    })
    expect(state.action).toBe('blocked')
    expect(state.reason).toMatch(/manipular/)
  })

  it('etapa em andamento fica rodando e os resultados chegam um a um', () => {
    const state = replay(HAPPY.slice(0, 3))

    expect(state.status).toBe('running')
    expect(state.nodes.guardrail).toBe('running')
    expect(state.nodes.triage).toBe('waiting')
    expect(state.outcomes.guardrail.map((o) => o.provider)).toEqual(['jev'])
    expect(currentNode(state)).toBe('guardrail')
  })

  it('run.started de uma nova execução limpa a anterior', () => {
    const first = replay([HAPPY[0], ...decision('guardrail', SAFE)])

    const second = reduceRun(first, { type: 'run.started', run_id: 'r2', node: null, data: {} })

    expect(second.runId).toBe('r2')
    expect(second.outcomes.guardrail).toEqual([])
    expect(second.nodes.guardrail).toBe('waiting')
  })
})

describe('failRun', () => {
  it('conexão caída encerra a execução em andamento com a mensagem', () => {
    const state = failRun(replay(HAPPY.slice(0, 3)), 'caiu')

    expect(state).toMatchObject({ status: 'failed', error: 'caiu' })
  })

  it('não mexe em execução já terminada', () => {
    const finished = replay(HAPPY)

    expect(failRun(finished, 'caiu')).toBe(finished)
    expect(failRun(initialRunState(), 'caiu').status).toBe('idle')
    expect(RUN).toBe('r1')
  })
})
