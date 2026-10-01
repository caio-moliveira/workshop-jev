import { useEffect, useMemo, useReducer, useRef, useState } from 'react'

import { ProviderBars } from '../components/charts/ProviderBars'
import { exportUrl, getBatchEstimate, getDataset, postBatch } from '../lib/api'
import {
  accuracyByQuestion,
  costByNode,
  filterRows,
  initialBatchState,
  latencyHistogram,
  reduceBatch,
  type RowFilter,
} from '../lib/batch'
import { formatMs, formatPercent, formatUsd } from '../lib/format'
import { subscribeBatch } from '../lib/sse'
import type { BatchEstimate, BatchReport, GraphConfig, ProviderName } from '../lib/types'

const PROVIDERS: { id: ProviderName; label: string }[] = [
  { id: 'jev', label: 'Jev' },
  { id: 'llm', label: 'LLM' },
]

const ACTION_LABEL = { auto: 'automática', human: 'humano', blocked: 'bloqueado' }

const FILTERS: { id: RowFilter; label: string }[] = [
  { id: 'all', label: 'Todos' },
  { id: 'disagree', label: 'Só discordâncias' },
  { id: 'errors', label: 'Só erros' },
]

function mean(values: number[]): number | null {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
}

function SummaryCards({ report }: { report: BatchReport }) {
  const agreement = mean(Object.values(report.agreement))
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {PROVIDERS.map(({ id, label }) => {
        const summary = report.by_provider[id]
        if (!summary) return null
        return (
          <article key={id} className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-3 font-semibold">
              {label} <span className="text-xs font-normal text-slate-500">{summary.model}</span>
            </h3>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <dt className="text-xs text-slate-500">Acurácia média</dt>
                <dd className="text-xl font-semibold">
                  {summary.accuracy == null ? '—' : formatPercent(summary.accuracy)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Custo total</dt>
                <dd className="text-xl font-semibold">{formatUsd(summary.cost_total)}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Por 1.000 tickets</dt>
                <dd className="text-xl font-semibold">{formatUsd(summary.cost_per_1000)}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Latência p95</dt>
                <dd className="text-xl font-semibold">
                  {summary.latency_p95 == null ? '—' : formatMs(summary.latency_p95)}
                </dd>
              </div>
            </dl>
          </article>
        )
      })}
      <p className="text-sm text-slate-600 md:col-span-2">
        {report.n} tickets · modo {report.mode} · primário{' '}
        {report.primary === 'jev' ? 'Jev' : 'LLM'}
        {agreement != null && <> · concordância média {formatPercent(agreement)}</>}
        {report.errors > 0 && <> · {report.errors} com erro de execução</>}
        {' · '}custos sem o node de resposta, que é só LLM
      </p>
    </div>
  )
}

interface Props {
  config: GraphConfig
  onOpenTicket: (ticketId: string) => void
}

export function Batch({ config, onOpenTicket }: Props) {
  const [n, setN] = useState(100)
  const [tag, setTag] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [estimate, setEstimate] = useState<BatchEstimate | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<RowFilter>('all')
  const [batch, dispatch] = useReducer(reduceBatch, initialBatchState())
  const unsubscribe = useRef<(() => void) | null>(null)

  useEffect(() => {
    getDataset()
      .then((tickets) => setTags([...new Set(tickets.flatMap((t) => t.tags))].sort()))
      .catch((e: Error) => setError(e.message))
    return () => unsubscribe.current?.()
  }, [])

  useEffect(() => {
    getBatchEstimate(n, tag || undefined)
      .then(setEstimate)
      .catch(() => setEstimate(null))
  }, [n, tag, config])

  async function execute() {
    setError(null)
    unsubscribe.current?.()
    try {
      const { batch_id, n: total } = await postBatch(n, tag || undefined)
      dispatch({ type: 'batch.started', batch_id, data: { n: total } })
      unsubscribe.current = subscribeBatch(batch_id, dispatch)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const report = batch.report
  const charts = useMemo(
    () =>
      report && {
        latency: latencyHistogram(report),
        cost: costByNode(report),
        accuracy: accuracyByQuestion(report),
      },
    [report],
  )
  const rows = report ? filterRows(report.tickets, filter) : []
  const progress = batch.total ? batch.done / batch.total : 0

  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-sm">
            Tickets
            <input
              type="number"
              min={1}
              max={330}
              value={n}
              onChange={(e) => setN(Math.max(1, Math.min(330, Number(e.target.value))))}
              className="w-24 rounded border border-slate-300 px-2 py-1"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Tag
            <select
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              className="rounded border border-slate-300 px-2 py-1"
            >
              <option value="">todas</option>
              {tags.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={execute}
            disabled={batch.status === 'running' || estimate?.n === 0}
            className="rounded bg-indigo-600 px-4 py-1.5 font-medium text-white disabled:opacity-40"
          >
            {batch.status === 'running' ? 'Executando…' : 'Executar lote'}
          </button>
          {estimate && (
            <span className="text-sm text-slate-600">
              {estimate.n} tickets
              {estimate.n < n && config.mode === 'replay' && ' (só os que têm gravação)'} · custo
              estimado{' '}
              {estimate.estimated_cost_usd == null
                ? 'indisponível (falta preço ou gravação)'
                : `até ${formatUsd(estimate.estimated_cost_usd)}`}
              {config.mode === 'replay' && ', não cobrado em replay'}
            </span>
          )}
        </div>
        {batch.status !== 'idle' && (
          <div className="flex items-center gap-3">
            <div
              className="h-2 flex-1 overflow-hidden rounded bg-slate-100"
              role="progressbar"
              aria-valuenow={batch.done}
              aria-valuemax={batch.total}
            >
              <div className="h-full bg-indigo-600" style={{ width: `${progress * 100}%` }} />
            </div>
            <span className="text-sm text-slate-600 tabular-nums">
              {batch.done} / {batch.total}
            </span>
          </div>
        )}
        {error && <p className="text-sm text-red-700">{error}</p>}
      </section>

      {report && charts && (
        <>
          <SummaryCards report={report} />

          <div className="grid gap-4 lg:grid-cols-2">
            <ProviderBars
              title="Distribuição de latência por chamada de decisão"
              data={charts.latency}
              category="label"
              format={(v) => String(v)}
              yLabel="chamadas"
            />
            <ProviderBars
              title="Custo por node (US$)"
              data={charts.cost}
              category="node"
              format={formatUsd}
            />
            <ProviderBars
              title="Acurácia por pergunta (%)"
              data={charts.accuracy}
              category="question"
              format={(v) => `${v}%`}
            />
          </div>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              {FILTERS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setFilter(id)}
                  className={`rounded px-3 py-1 text-sm ${
                    filter === id ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'
                  }`}
                >
                  {label}
                </button>
              ))}
              <span className="text-sm text-slate-500">{rows.length} tickets</span>
              <span className="ml-auto flex gap-2">
                {(['csv', 'json'] as const).map((format) => (
                  <a
                    key={format}
                    href={exportUrl(report.batch_id, format)}
                    download
                    className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50"
                  >
                    Exportar {format.toUpperCase()}
                  </a>
                ))}
              </span>
            </div>
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white text-xs text-slate-500">
                  <tr>
                    <th className="py-1 pr-3">Ticket</th>
                    <th className="pr-3">Fila (gabarito)</th>
                    <th className="pr-3">Jev</th>
                    <th className="pr-3">LLM</th>
                    <th className="pr-3">Ação</th>
                    <th>Tags</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.ticket_id}
                      onClick={() => onOpenTicket(row.ticket_id)}
                      className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                    >
                      <td className="py-1 pr-3 font-mono text-xs">{row.ticket_id}</td>
                      <td className="pr-3">{String(row.labels.fila ?? '—')}</td>
                      <td className="pr-3">{String(row.answers.fila?.jev ?? '—')}</td>
                      <td className="pr-3">{String(row.answers.fila?.llm ?? '—')}</td>
                      <td className="pr-3">
                        {row.action ? ACTION_LABEL[row.action] : '—'}
                        {row.disagrees && <span className="ml-1 text-amber-700">· discorda</span>}
                        {row.wrong && <span className="ml-1 text-red-700">· errou</span>}
                        {row.has_error && <span className="ml-1 text-red-700">· falha</span>}
                      </td>
                      <td className="text-xs text-slate-500">{row.tags.join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
