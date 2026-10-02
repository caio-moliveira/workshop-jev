import { useEffect, useMemo, useReducer, useRef, useState } from 'react'

import { ProviderBars } from '../components/charts/ProviderBars'
import { Badge, Button, Card, CardTitle, EmptyState, cx, type Tone } from '../components/ui'
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
import { toolLabel } from '../lib/questions'
import { subscribeBatch } from '../lib/sse'
import type {
  Action,
  BatchEstimate,
  BatchReport,
  GraphConfig,
  ProviderName,
  Question,
} from '../lib/types'

const PROVIDERS: { id: ProviderName; label: string; dot: string }[] = [
  { id: 'jev', label: 'Jev', dot: 'bg-jev' },
  { id: 'llm', label: 'LLM', dot: 'bg-llm' },
]

const ACTION: Record<Action, { label: string; tone: Tone }> = {
  auto: { label: 'liberada', tone: 'ok' },
  human: { label: 'revisão', tone: 'warn' },
  blocked: { label: 'bloqueada', tone: 'danger' },
}

const FILTERS: { id: RowFilter; label: string }[] = [
  { id: 'all', label: 'Todas' },
  { id: 'disagree', label: 'Só discordâncias' },
  { id: 'errors', label: 'Só erros' },
]

const MAX_BATCH = 100

function mean(values: number[]): number | null {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={cx('font-semibold tabular-nums', strong ? 'text-2xl' : 'text-lg')}>{value}</dd>
    </div>
  )
}

function SummaryCards({ report }: { report: BatchReport }) {
  const agreement = mean(Object.values(report.agreement))
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {PROVIDERS.map(({ id, label, dot }) => {
        const summary = report.by_provider[id]
        if (!summary) return null
        const tool = report.by_question.tool?.[id]
        return (
          <Card key={id} className="p-4">
            <h3 className="mb-3 flex items-center gap-2 font-semibold">
              <span className={cx('size-2.5 rounded-full', dot)} aria-hidden="true" />
              {label}
              <span className="text-xs font-normal text-slate-500">{summary.model}</span>
              {report.primary === id && <Badge tone="brand">primário</Badge>}
            </h3>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat
                strong
                label="Acerto da consulta"
                value={tool?.accuracy == null ? '—' : formatPercent(tool.accuracy)}
              />
              <Stat label="Custo total" value={formatUsd(summary.cost_total)} />
              <Stat label="Por 1.000 perguntas" value={formatUsd(summary.cost_per_1000)} />
              <Stat
                label="Latência p95"
                value={summary.latency_p95 == null ? '—' : formatMs(summary.latency_p95)}
              />
            </dl>
          </Card>
        )
      })}
      <p className="text-sm text-slate-600 md:col-span-2">
        {report.n} perguntas · modo {report.mode}
        {agreement != null && <> · concordância média {formatPercent(agreement)}</>}
        {report.errors > 0 && <> · {report.errors} com erro de execução</>}
        {' · '}custos sem a etapa de resposta, que é só LLM
      </p>
    </div>
  )
}

interface Props {
  config: GraphConfig
  onOpenQuestion: (questionId: string) => void
}

export function Batch({ config, onOpenQuestion }: Props) {
  const [n, setN] = useState(MAX_BATCH)
  const [tag, setTag] = useState('')
  const [questions, setQuestions] = useState<Question[]>([])
  const [estimate, setEstimate] = useState<BatchEstimate | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<RowFilter>('all')
  const [batch, dispatch] = useReducer(reduceBatch, initialBatchState())
  const unsubscribe = useRef<(() => void) | null>(null)

  useEffect(() => {
    getDataset()
      .then(setQuestions)
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

  const tags = useMemo(() => [...new Set(questions.flatMap((q) => q.tags))].sort(), [questions])
  const texts = useMemo(() => new Map(questions.map((q) => [q.id, q.text])), [questions])
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
  const rows = report ? filterRows(report.questions, filter) : []
  const progress = batch.total ? batch.done / batch.total : 0

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle hint="Roda várias perguntas do golden set e compara Jev e LLM em acerto, custo e latência.">
          Lote
        </CardTitle>
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-sm">
            Perguntas
            <input
              type="number"
              min={1}
              max={MAX_BATCH}
              value={n}
              onChange={(e) => setN(Math.max(1, Math.min(MAX_BATCH, Number(e.target.value))))}
              className="w-24 rounded-lg border border-slate-300 px-3 py-2 tabular-nums"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Tag
            <select
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2"
            >
              <option value="">todas</option>
              {tags.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <Button
            onClick={execute}
            disabled={estimate?.n === 0}
            loading={batch.status === 'running'}
          >
            {batch.status === 'running' ? 'Executando' : 'Executar lote'}
          </Button>
        </div>
        {estimate && (
          <p className="mt-3 text-sm text-slate-600">
            {estimate.n} perguntas
            {estimate.n < n && config.mode === 'replay' && ' (só as que têm gravação)'} · custo
            estimado{' '}
            {estimate.estimated_cost_usd == null
              ? 'indisponível (falta preço ou gravação)'
              : `até ${formatUsd(estimate.estimated_cost_usd)}`}
            {config.mode === 'replay' && ', não cobrado em replay'}
          </p>
        )}
        {batch.status !== 'idle' && (
          <div className="mt-4 flex items-center gap-3">
            <div
              className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"
              role="progressbar"
              aria-label="Progresso do lote"
              aria-valuemin={0}
              aria-valuenow={batch.done}
              aria-valuemax={batch.total}
            >
              <div
                className="bg-brand-600 h-full rounded-full transition-[width] motion-reduce:transition-none"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <span className="text-sm text-slate-600 tabular-nums">
              {batch.done} / {batch.total}
            </span>
          </div>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {error}
          </p>
        )}
      </Card>

      {!report && batch.status === 'idle' && (
        <Card>
          <EmptyState title="Nenhum lote executado ainda">
            Escolha quantas perguntas rodar e clique em Executar lote. O relatório aparece aqui.
          </EmptyState>
        </Card>
      )}

      {report && charts && (
        <>
          <SummaryCards report={report} />

          <div className="grid gap-4 lg:grid-cols-2">
            <ProviderBars
              title="Acerto por pergunta (%)"
              data={charts.accuracy}
              category="question"
              format={(v) => `${v}%`}
            />
            <ProviderBars
              title="Latência por chamada de decisão"
              data={charts.latency}
              category="label"
              format={(v) => String(v)}
              yLabel="chamadas"
            />
            <ProviderBars
              title="Custo por etapa (US$)"
              data={charts.cost}
              category="node"
              format={formatUsd}
            />
          </div>

          <Card className="p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <div role="group" aria-label="Filtro" className="flex rounded-lg bg-slate-100 p-1">
                {FILTERS.map(({ id, label }) => (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={filter === id}
                    onClick={() => setFilter(id)}
                    className={cx(
                      'rounded-md px-3 py-1 text-sm font-medium',
                      filter === id
                        ? 'bg-white text-slate-900 shadow-sm'
                        : 'text-slate-600 hover:text-slate-900',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <span className="text-sm text-slate-500">{rows.length} perguntas</span>
              <span className="ml-auto flex gap-2">
                {(['csv', 'json'] as const).map((format) => (
                  <a
                    key={format}
                    href={exportUrl(report.batch_id, format)}
                    download
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
                  >
                    Exportar {format.toUpperCase()}
                  </a>
                ))}
              </span>
            </div>
            <div className="max-h-[28rem] overflow-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">
                  Perguntas do lote. Clique numa pergunta para abri-la no Playground.
                </caption>
                <thead className="sticky top-0 bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Pergunta
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Consulta esperada
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Jev
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      LLM
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Resultado
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const label = row.labels.tool
                    const cell = (provider: ProviderName) => {
                      const value = row.answers.tool?.[provider]
                      if (value == null) return <span className="text-slate-400">—</span>
                      const hit = label !== undefined && value === label
                      return (
                        <span className={hit ? 'text-slate-700' : 'font-medium text-red-700'}>
                          {toolLabel(String(value))}
                        </span>
                      )
                    }
                    return (
                      <tr
                        key={row.question_id}
                        className="border-t border-slate-100 hover:bg-slate-50"
                      >
                        <td className="max-w-xs px-3 py-2">
                          <button
                            type="button"
                            onClick={() => onOpenQuestion(row.question_id)}
                            className="text-brand-700 block w-full truncate text-left hover:underline"
                            title={`Abrir ${row.question_id} no Playground`}
                          >
                            {texts.get(row.question_id) ?? row.question_id}
                          </button>
                        </td>
                        <td className="px-3 py-2 text-slate-600">
                          {label === undefined ? '—' : toolLabel(String(label))}
                        </td>
                        <td className="px-3 py-2">{cell('jev')}</td>
                        <td className="px-3 py-2">{cell('llm')}</td>
                        <td className="px-3 py-2">
                          <span className="flex flex-wrap gap-1">
                            {row.action && (
                              <Badge tone={ACTION[row.action].tone}>
                                {ACTION[row.action].label}
                              </Badge>
                            )}
                            {row.disagrees && <Badge tone="warn">discordam</Badge>}
                            {row.wrong && <Badge tone="danger">errou</Badge>}
                            {row.has_error && <Badge tone="danger">falha</Badge>}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
