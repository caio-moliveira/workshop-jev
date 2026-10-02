import { formatPercent } from './format'
import { toolLabel } from './questions'
import type { RunViewState } from './runState'
import {
  isError,
  isToolError,
  type NodeMetric,
  type NodeName,
  type ProviderName,
  type Thresholds,
} from './types'

export type StepTone = 'waiting' | 'running' | 'ok' | 'warn' | 'blocked' | 'error' | 'skipped'

export interface StepTiming {
  label: string
  provider?: ProviderName
  ms: number
}

export interface StepSummary {
  tone: StepTone
  text: string
  timings: StepTiming[]
}

const PROVIDER_LABEL: Record<ProviderName, string> = { jev: 'Jev', llm: 'LLM' }

const blockedText = (reason: string | null) => (reason ? `Bloqueada: ${reason}` : 'Bloqueada')

function providerTimings(run: RunViewState, node: NodeName): StepTiming[] {
  return run.outcomes[node]
    .filter((o): o is NodeMetric => !isError(o))
    .map((o) => ({ label: PROVIDER_LABEL[o.provider], provider: o.provider, ms: o.latency_ms }))
}

/** A frase, o tom e os tempos de uma etapa, a partir do estado da execução. Função pura. */
export function stepSummary(
  node: NodeName,
  run: RunViewState,
  thresholds: Thresholds,
): StepSummary {
  const status = run.nodes[node]
  const timings = providerTimings(run, node)
  if (status === 'waiting') {
    return { tone: run.status === 'failed' ? 'skipped' : 'waiting', text: 'Aguardando', timings }
  }
  if (status === 'running') return { tone: 'running', text: 'Em andamento…', timings }
  if (status === 'skipped') return { tone: 'skipped', text: 'Não executada', timings }
  if (status === 'blocked') {
    return { tone: 'blocked', text: blockedText(run.reason), timings }
  }

  switch (node) {
    case 'guardrail': {
      const answers = run.answers.guardrail
      if (!answers) return { tone: 'error', text: 'A decisão falhou', timings }
      const risky = Object.values(answers).some(
        (a) => Number(a.value) >= thresholds.guardrail_block,
      )
      return risky
        ? { tone: 'blocked', text: blockedText(run.reason), timings }
        : { tone: 'ok', text: 'Pergunta segura', timings }
    }
    case 'triage': {
      const answer = run.answers.triage?.tool
      if (!answer) return { tone: 'error', text: 'A decisão falhou', timings }
      const name = String(answer.value)
      if (name === 'nenhuma') {
        return { tone: 'warn', text: 'Nenhuma consulta responde a pergunta', timings }
      }
      const confidence = answer.confidence ?? 0
      const text = `${toolLabel(name)} · confiança ${formatPercent(confidence)}`
      return {
        tone: confidence < thresholds.triage_min_confidence ? 'warn' : 'ok',
        text,
        timings,
      }
    }
    case 'tool': {
      const tool = run.tool
      if (!tool || isToolError(tool)) {
        return { tone: 'error', text: 'A consulta falhou', timings: [] }
      }
      const rows = tool.row_count === 1 ? '1 linha' : `${tool.row_count} linhas`
      return {
        tone: 'ok',
        text: `${rows} de ${tool.view}`,
        timings: [{ label: 'SQL', ms: tool.latency_ms }],
      }
    }
    case 'reply':
      return run.draftReply
        ? { tone: 'ok', text: 'Resposta escrita com os dados', timings }
        : { tone: 'error', text: 'A resposta não foi gerada', timings }
    case 'verify': {
      const answers = run.answers.verify
      if (!answers) return { tone: 'error', text: 'A decisão falhou', timings }
      const faithful = Number(answers.fiel_aos_dados?.value ?? 0)
      const invented = Number(answers.inventa_numero?.value ?? 0)
      const failed =
        faithful < thresholds.verify_min_faithful || invented >= thresholds.verify_max_invented
      return {
        tone: failed ? 'warn' : 'ok',
        text: `Fiel aos dados ${formatPercent(faithful)} · número inventado ${formatPercent(invented)}`,
        timings,
      }
    }
    case 'act':
      if (run.action === 'auto') return { tone: 'ok', text: 'Resposta liberada', timings: [] }
      return {
        tone: 'warn',
        text: run.reason ? `Revisão humana: ${run.reason}` : 'Revisão humana',
        timings: [],
      }
  }
}
