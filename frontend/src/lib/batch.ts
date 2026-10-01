import { NODE_LABELS, QUESTIONS } from './questions'
import type { BatchEvent, BatchReport, NodeName, ProviderName, TicketRow } from './types'

export interface BatchViewState {
  batchId: string | null
  status: 'idle' | 'running' | 'finished'
  done: number
  total: number
  report: BatchReport | null
}

export const initialBatchState = (batchId: string | null = null): BatchViewState => ({
  batchId,
  status: batchId ? 'running' : 'idle',
  done: 0,
  total: 0,
  report: null,
})

/** Transforma os eventos SSE do lote no estado da tela. Função pura. */
export function reduceBatch(state: BatchViewState, event: BatchEvent): BatchViewState {
  switch (event.type) {
    case 'batch.started':
      return { ...initialBatchState(event.batch_id), total: event.data.n }
    case 'batch.progress':
      return { ...state, done: event.data.done, total: event.data.total }
    case 'batch.finished':
      return { ...state, status: 'finished', done: event.data.n, report: event.data }
  }
}

// Faixas em escala aproximadamente logarítmica: o Jev responde em dezenas de ms e o LLM
// em segundos. Com faixas lineares, um dos dois ficaria espremido numa barra só.
export const LATENCY_BINS = [
  { label: '< 50 ms', max: 50 },
  { label: '50–100 ms', max: 100 },
  { label: '100–250 ms', max: 250 },
  { label: '250–500 ms', max: 500 },
  { label: '0,5–1 s', max: 1000 },
  { label: '1–2 s', max: 2000 },
  { label: '2–5 s', max: 5000 },
  { label: '≥ 5 s', max: Infinity },
]

const DECISION: NodeName[] = ['guardrail', 'triage', 'verify']
const PROVIDERS: ProviderName[] = ['jev', 'llm']

/** Chamadas de decisão por faixa de latência e por provider. O `reply` fica de fora. */
export function latencyHistogram(report: BatchReport) {
  const bins = LATENCY_BINS.map((bin) => ({ label: bin.label, jev: 0, llm: 0 }))
  for (const node of DECISION) {
    for (const provider of PROVIDERS) {
      for (const latency of report.by_node[node]?.[provider]?.latencies ?? []) {
        bins[LATENCY_BINS.findIndex((bin) => latency < bin.max)][provider] += 1
      }
    }
  }
  return bins
}

export function costByNode(report: BatchReport) {
  const nodes: NodeName[] = ['guardrail', 'triage', 'verify', 'reply']
  return nodes
    .filter((node) => report.by_node[node])
    .map((node) => ({
      node: NODE_LABELS[node],
      jev: report.by_node[node].jev?.cost_total ?? 0,
      llm: report.by_node[node].llm?.cost_total ?? 0,
    }))
}

const QUESTION_LABELS: Record<string, string> = Object.fromEntries(
  Object.values(QUESTIONS)
    .flat()
    .map((q) => [q.name, q.label]),
)

const toPercent = (value: number | null | undefined) =>
  value == null ? null : Math.round(value * 1000) / 10

/** Acurácia em percentual, só das perguntas que têm rótulo no golden set. */
export function accuracyByQuestion(report: BatchReport) {
  return Object.entries(report.by_question)
    .filter(([, summaries]) => PROVIDERS.some((p) => summaries[p]?.accuracy != null))
    .map(([question, summaries]) => ({
      question: QUESTION_LABELS[question] ?? question,
      jev: toPercent(summaries.jev?.accuracy),
      llm: toPercent(summaries.llm?.accuracy),
    }))
}

export type RowFilter = 'all' | 'disagree' | 'errors'

export function filterRows(rows: TicketRow[], filter: RowFilter): TicketRow[] {
  if (filter === 'disagree') return rows.filter((r) => r.disagrees)
  if (filter === 'errors') return rows.filter((r) => r.wrong || r.has_error)
  return rows
}
