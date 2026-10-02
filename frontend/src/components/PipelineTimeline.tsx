import { disagreements } from '../lib/diff'
import { formatMs } from '../lib/format'
import { NODE_HINTS, NODE_LABELS, isDecisionNode, toolLabel } from '../lib/questions'
import { NODES, type RunViewState } from '../lib/runState'
import { stepSummary, type StepSummary, type StepTone } from '../lib/steps'
import { isToolError, type NodeName, type Thresholds } from '../lib/types'
import { DiffBadge } from './DiffBadge'
import { ProviderCard } from './ProviderCard'
import { DataTable, Spinner, cx } from './ui'

const TONE: Record<StepTone, { ring: string; text: string; label: string }> = {
  waiting: {
    ring: 'border-slate-300 bg-white text-slate-400',
    text: 'text-slate-500',
    label: 'aguardando',
  },
  running: {
    ring: 'border-brand-500 bg-brand-50 text-brand-600 animate-pulse-ring',
    text: 'text-brand-700',
    label: 'em andamento',
  },
  ok: { ring: 'border-ok bg-ok text-white', text: 'text-slate-700', label: 'concluída' },
  warn: { ring: 'border-warn bg-warn text-white', text: 'text-amber-800', label: 'atenção' },
  blocked: { ring: 'border-danger bg-danger text-white', text: 'text-red-700', label: 'bloqueada' },
  error: { ring: 'border-danger bg-white text-danger', text: 'text-red-700', label: 'falhou' },
  skipped: {
    ring: 'border-dashed border-slate-300 bg-slate-50 text-slate-300',
    text: 'text-slate-400',
    label: 'não executada',
  },
}

function StepIcon({ tone }: { tone: StepTone }) {
  const glyph: Partial<Record<StepTone, string>> = {
    ok: 'M5 12.5l4.5 4.5L19 7.5',
    warn: 'M12 7v6m0 4h.01',
    blocked: 'M7 7l10 10M17 7L7 17',
    error: 'M12 7v6m0 4h.01',
    skipped: 'M7 12h10',
  }
  return (
    <span
      className={cx(
        'relative z-10 flex size-7 shrink-0 items-center justify-center rounded-full border-2',
        TONE[tone].ring,
      )}
    >
      {tone === 'running' ? (
        <Spinner className="size-4" />
      ) : glyph[tone] ? (
        <svg viewBox="0 0 24 24" className="size-4" fill="none" aria-hidden="true">
          <path d={glyph[tone]} stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      ) : (
        <span className="size-1.5 rounded-full bg-current" />
      )}
      <span className="sr-only">{TONE[tone].label}</span>
    </span>
  )
}

function Timings({ summary }: { summary: StepSummary }) {
  if (summary.timings.length === 0) return null
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-500 tabular-nums">
      {summary.timings.map((t) => (
        <span key={t.label} className="inline-flex items-center gap-1">
          <span
            aria-hidden="true"
            className={cx(
              'size-1.5 rounded-full',
              t.provider === 'jev' ? 'bg-jev' : t.provider === 'llm' ? 'bg-llm' : 'bg-slate-400',
            )}
          />
          {t.label} {formatMs(t.ms)}
        </span>
      ))}
    </span>
  )
}

function Details({ node, run }: { node: NodeName; run: RunViewState }) {
  if (node === 'tool') {
    const tool = run.tool
    if (!tool) return null
    if (isToolError(tool)) {
      return <p className="text-sm text-red-700">Erro na consulta: {tool.error}</p>
    }
    return (
      <div className="flex flex-col gap-2">
        <p className="text-xs text-slate-500">
          {toolLabel(tool.tool)} · <code className="font-mono">SELECT * FROM {tool.view}</code>
          {tool.truncated && ' · resultado cortado'}
        </p>
        <DataTable
          columns={tool.columns}
          rows={tool.rows}
          caption={`Dados retornados por ${tool.view}`}
        />
      </div>
    )
  }
  const outcomes = run.outcomes[node]
  if (outcomes.length === 0) return null
  const diffs = isDecisionNode(node) ? disagreements(node, outcomes) : new Set<string>()
  return (
    <div className={cx('grid gap-3', outcomes.length > 1 && 'md:grid-cols-2')}>
      {outcomes.map((outcome) => (
        <ProviderCard
          key={outcome.provider}
          node={isDecisionNode(node) ? node : 'reply'}
          outcome={outcome}
          disagreements={diffs}
        />
      ))}
    </div>
  )
}

function detailsLabel(node: NodeName, run: RunViewState): string {
  if (node === 'tool') return 'Ver dados'
  if (node === 'reply') return 'Ver custo'
  return run.outcomes[node].length > 1 ? 'Comparar Jev × LLM' : 'Ver resposta do modelo'
}

interface Props {
  run: RunViewState
  thresholds: Thresholds
  /** Esconde a dica de cada etapa: na visão lado a lado as colunas são estreitas. */
  compact?: boolean
}

/** As seis etapas do agente, em ordem, com o estado de cada uma e o detalhe sob demanda. */
export function PipelineTimeline({ run, thresholds, compact = false }: Props) {
  return (
    <ol className="relative flex flex-col" aria-label="Etapas do agente">
      {NODES.map((node, index) => {
        const summary = stepSummary(node, run, thresholds)
        const hasDetails = node === 'tool' ? run.tool !== null : run.outcomes[node].length > 0
        const disagree = isDecisionNode(node) && disagreements(node, run.outcomes[node]).size > 0
        const last = index === NODES.length - 1
        return (
          <li
            key={node}
            data-testid={`step-${node}`}
            data-tone={summary.tone}
            className="relative flex gap-3 pb-4 last:pb-0"
          >
            {!last && (
              <span
                aria-hidden="true"
                className={cx(
                  'absolute top-7 left-3.5 -ml-px h-[calc(100%-1.75rem)] w-0.5',
                  summary.tone === 'waiting' || summary.tone === 'skipped'
                    ? 'bg-slate-200'
                    : 'bg-slate-300',
                )}
              />
            )}
            <StepIcon tone={summary.tone} />
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <h3
                  className={cx(
                    'text-sm font-semibold',
                    summary.tone === 'skipped' ? 'text-slate-400' : 'text-slate-900',
                  )}
                >
                  {NODE_LABELS[node]}
                  <span
                    className={cx(
                      'ml-2 hidden text-xs font-normal text-slate-400',
                      !compact && 'sm:inline',
                    )}
                  >
                    {NODE_HINTS[node]}
                  </span>
                </h3>
                <Timings summary={summary} />
              </div>
              <p className={cx('mt-0.5 text-sm', TONE[summary.tone].text)}>
                {summary.text}
                {disagree && (
                  <span className="ml-2 align-middle">
                    <DiffBadge />
                  </span>
                )}
              </p>
              {hasDetails && node !== 'act' && (
                <details className="group mt-2">
                  <summary className="text-brand-600 hover:text-brand-700 inline-flex items-center gap-1 rounded text-xs font-medium select-none [&::-webkit-details-marker]:hidden">
                    <svg
                      viewBox="0 0 24 24"
                      className="size-3.5 transition-transform group-open:rotate-90 motion-reduce:transition-none"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d="M9 6l6 6-6 6"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                      />
                    </svg>
                    {detailsLabel(node, run)}
                  </summary>
                  <div className="mt-3">
                    <Details node={node} run={run} />
                  </div>
                </details>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
