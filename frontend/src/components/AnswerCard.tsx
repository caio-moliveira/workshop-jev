import { formatMs, formatUsd } from '../lib/format'
import { NODE_LABELS } from '../lib/questions'
import { currentNode, runTotals, type RunViewState } from '../lib/runState'
import type { Action } from '../lib/types'
import { Markdown } from './Markdown'
import { Badge, Card, EmptyState, Skeleton, cx, type Tone } from './ui'

export const ACTION: Record<Action, { label: string; tone: Tone }> = {
  auto: { label: 'Resposta liberada', tone: 'ok' },
  human: { label: 'Revisão humana', tone: 'warn' },
  blocked: { label: 'Pergunta bloqueada', tone: 'danger' },
}

interface Props {
  run: RunViewState
  /** Na visão lado a lado o cartão é menor: sem o texto de boas-vindas. */
  compact?: boolean
}

/** O resultado final de uma execução: a resposta, a ação, o motivo e o que custou. */
export function AnswerCard({ run, compact = false }: Props) {
  if (run.status === 'idle') {
    return (
      <Card>
        <EmptyState
          title="A resposta aparece aqui"
          icon={
            <svg viewBox="0 0 24 24" className="size-8" fill="none" aria-hidden="true">
              <path
                d="M4 5h16v11H8l-4 4V5z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </svg>
          }
        >
          {!compact &&
            'Faça uma pergunta sobre as vendas. Ao lado, você acompanha cada etapa que o agente percorre até responder.'}
        </EmptyState>
      </Card>
    )
  }

  if (run.status === 'running') {
    const node = currentNode(run)
    return (
      <Card aria-busy="true">
        <p className="text-brand-700 mb-4 text-sm font-medium">
          Agente trabalhando{node ? `: ${NODE_LABELS[node].toLowerCase()}` : '…'}
        </p>
        <div className="flex flex-col gap-2">
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </Card>
    )
  }

  if (run.status === 'failed') {
    return (
      <Card className="border-red-200">
        <p className="font-medium text-red-800">A execução não terminou</p>
        <p className="mt-1 text-sm text-red-700">{run.error}</p>
      </Card>
    )
  }

  const result = run.result
  const action = run.action ? ACTION[run.action] : null
  const totals = runTotals(run)
  const held = run.action !== 'auto'
  return (
    <Card className={cx(run.action === 'blocked' && 'border-red-200')}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Resposta</h2>
        {action && <Badge tone={action.tone}>{action.label}</Badge>}
      </div>

      {run.draftReply ? (
        <>
          {held && (
            <p className="mb-1 text-xs font-medium tracking-wide text-amber-700 uppercase">
              Rascunho retido para revisão
            </p>
          )}
          <Markdown
            className={cx(
              'text-[15px] leading-relaxed',
              held ? 'text-slate-500' : 'text-slate-800',
            )}
          >
            {run.draftReply}
          </Markdown>
        </>
      ) : (
        <p className="text-sm text-slate-500">O agente não escreveu resposta para esta pergunta.</p>
      )}

      {run.reason && (
        <p
          className={cx(
            'mt-4 rounded-lg px-3 py-2 text-sm',
            run.action === 'blocked'
              ? 'bg-danger-soft text-red-800'
              : 'bg-warn-soft text-amber-900',
          )}
        >
          <span className="font-medium">Por quê: </span>
          {run.reason}
        </p>
      )}

      <dl className="mt-4 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-100 pt-3 text-xs text-slate-500">
        {result?.tool_result && (
          <div className="flex gap-1">
            <dt>Fonte:</dt>
            <dd className="font-mono">{result.tool_result.view}</dd>
          </div>
        )}
        <div className="flex gap-1">
          <dt>Tempo somado:</dt>
          <dd className="tabular-nums">{formatMs(totals.ms)}</dd>
        </div>
        <div className="flex gap-1">
          <dt>Custo dos modelos:</dt>
          <dd className="tabular-nums">{formatUsd(totals.cost)}</dd>
        </div>
      </dl>

      {result && result.errors.length > 0 && (
        <details className="mt-3 text-xs">
          <summary className="text-slate-500 hover:text-slate-700">
            {result.errors.length === 1
              ? '1 aviso técnico'
              : `${result.errors.length} avisos técnicos`}
          </summary>
          <ul className="mt-2 flex flex-col gap-1 font-mono text-red-700">
            {result.errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  )
}
