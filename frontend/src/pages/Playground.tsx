import { useEffect, useReducer, useRef, useState } from 'react'

import { PipelineTimeline } from '../components/PipelineTimeline'
import {
  Badge,
  Button,
  Card,
  CardTitle,
  EmptyState,
  Skeleton,
  cx,
  type Tone,
} from '../components/ui'
import { getDataset, postRun } from '../lib/api'
import { formatUsd } from '../lib/format'
import { NODE_LABELS, toolLabel } from '../lib/questions'
import {
  currentNode,
  failRun,
  initialRunState,
  reduceRun,
  type RunViewState,
} from '../lib/runState'
import { subscribeRun } from '../lib/sse'
import type { Action, GraphConfig, Question, RunEvent } from '../lib/types'

const ACTION: Record<Action, { label: string; tone: Tone }> = {
  auto: { label: 'Resposta liberada', tone: 'ok' },
  human: { label: 'Revisão humana', tone: 'warn' },
  blocked: { label: 'Pergunta bloqueada', tone: 'danger' },
}

const RISKS: Record<string, string> = {
  injection: 'tentativa de manipulação',
  dado_sensivel: 'dado sensível',
  fora_escopo: 'fora do escopo',
}

type Dispatch = RunEvent | { type: 'failed'; error: string }

function reducer(state: RunViewState, action: Dispatch): RunViewState {
  return action.type === 'failed' ? failRun(state, action.error) : reduceRun(state, action)
}

function expected(question: Question): string {
  const risks = Object.entries(question.guardrail)
    .filter(([, flagged]) => flagged)
    .map(([risk]) => RISKS[risk])
  if (risks.length) return `deve ser bloqueada (${risks.join(', ')})`
  return `consulta esperada: ${toolLabel(question.labels.tool)}`
}

function AnswerCard({ run }: { run: RunViewState }) {
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
          Faça uma pergunta sobre as vendas. Ao lado, você acompanha cada etapa que o agente
          percorre até responder.
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
  const cost = result?.metrics.reduce((sum, m) => sum + m.cost_usd, 0) ?? 0
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
          <p
            className={cx(
              'text-[15px] leading-relaxed whitespace-pre-wrap',
              held ? 'text-slate-500' : 'text-slate-800',
            )}
          >
            {run.draftReply}
          </p>
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
          <dt>Custo dos modelos:</dt>
          <dd className="tabular-nums">{formatUsd(cost)}</dd>
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

interface Props {
  config: GraphConfig
  questionId?: string | null
}

export function Playground({ config, questionId }: Props) {
  const replay = config.mode === 'replay'
  const [questions, setQuestions] = useState<Question[]>([])
  const [selectedId, setSelectedId] = useState<string>(questionId ?? '')
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [run, dispatch] = useReducer(reducer, initialRunState())
  const unsubscribe = useRef<(() => void) | null>(null)

  useEffect(() => {
    getDataset()
      .then(setQuestions)
      .catch((e: Error) => setError(e.message))
    return () => unsubscribe.current?.()
  }, [])

  const examples = questions.filter((q) => q.replayable)
  const selected = questions.find((q) => q.id === selectedId)
  const value = selected ? selected.text : text
  const canRun = run.status !== 'running' && (selected ? true : !replay && text.trim() !== '')

  async function execute() {
    if (!canRun) return
    setError(null)
    unsubscribe.current?.()
    try {
      const body = selected ? { question_id: selected.id } : { text }
      const { run_id } = await postRun(body)
      dispatch({ type: 'run.started', run_id, node: null, data: { question: value } })
      unsubscribe.current = subscribeRun(run_id, dispatch, (message) =>
        dispatch({ type: 'failed', error: message }),
      )
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const node = currentNode(run)
  const announcement =
    run.status === 'running'
      ? node
        ? `Etapa em andamento: ${NODE_LABELS[node]}`
        : 'Execução iniciada'
      : run.status === 'finished' && run.action
        ? `Execução concluída: ${ACTION[run.action].label}`
        : ''

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            execute()
          }}
          className="flex flex-col gap-3"
        >
          <label htmlFor="question" className="text-sm font-medium text-slate-700">
            Pergunte sobre as vendas da Mercado Jornada
          </label>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
            <textarea
              id="question"
              rows={2}
              readOnly={replay}
              value={value}
              onChange={(e) => {
                setSelectedId('')
                setText(e.target.value)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) execute()
              }}
              placeholder={
                replay
                  ? 'Escolha uma pergunta abaixo. Em replay só rodam as que têm gravação.'
                  : 'Ex.: qual região vendeu mais em 2026?'
              }
              aria-describedby="question-help"
              className="focus:border-brand-500 min-h-16 flex-1 resize-y rounded-lg border border-slate-300 px-3 py-2 text-[15px] placeholder:text-slate-400 read-only:bg-slate-50"
            />
            <Button type="submit" disabled={!canRun} loading={run.status === 'running'}>
              {run.status === 'running' ? 'Executando' : 'Perguntar'}
            </Button>
          </div>
          <p id="question-help" className="text-xs text-slate-500">
            {selected ? (
              <>Gabarito do golden set: {expected(selected)}</>
            ) : replay ? (
              'Modo replay: respostas gravadas, sem chamar APIs nem o banco.'
            ) : (
              'Modo live: chama os modelos e o banco de verdade. Ctrl+Enter envia.'
            )}
          </p>
          {examples.length > 0 && (
            <div className="flex flex-wrap gap-2" aria-label="Perguntas de exemplo">
              {examples.map((q) => (
                <button
                  key={q.id}
                  type="button"
                  aria-pressed={q.id === selectedId}
                  onClick={() => setSelectedId(q.id === selectedId ? '' : q.id)}
                  className={cx(
                    'max-w-full truncate rounded-full border px-3 py-1 text-left text-sm transition-colors motion-reduce:transition-none',
                    q.id === selectedId
                      ? 'border-brand-500 bg-brand-50 text-brand-700'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900',
                  )}
                  title={q.text}
                >
                  {q.text}
                </button>
              ))}
            </div>
          )}
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
        </form>
      </Card>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <Card className="order-2 lg:order-1">
          <CardTitle hint="Cada etapa acende em tempo real. Abra uma etapa para ver o que Jev e LLM responderam.">
            Como o agente chegou lá
          </CardTitle>
          <PipelineTimeline run={run} thresholds={config.thresholds} />
        </Card>
        <div className="order-1 lg:sticky lg:top-20 lg:order-2">
          <AnswerCard run={run} />
        </div>
      </div>

      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </div>
  )
}
