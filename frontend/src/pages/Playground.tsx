import { useEffect, useState } from 'react'

import { ACTION, AnswerCard } from '../components/AnswerCard'
import { PipelineTimeline } from '../components/PipelineTimeline'
import { Button, Card, CardTitle, cx } from '../components/ui'
import { getDataset, type RunBody } from '../lib/api'
import { NODE_LABELS, toolLabel } from '../lib/questions'
import { currentNode, type RunViewState } from '../lib/runState'
import type { GraphConfig, ProviderName, Question } from '../lib/types'
import { useRun } from '../lib/useRun'

type View = 'compare' | 'single'

const VIEWS: { id: View; label: string }[] = [
  { id: 'compare', label: 'Jev × LLM lado a lado' },
  { id: 'single', label: 'Fluxo único' },
]

const PIPELINES: { id: ProviderName; title: string; dot: string; bar: string }[] = [
  { id: 'jev', title: 'Pipeline Jev', dot: 'bg-jev', bar: 'border-jev' },
  { id: 'llm', title: 'Pipeline LLM', dot: 'bg-llm', bar: 'border-llm' },
]

const RISKS: Record<string, string> = {
  injection: 'tentativa de manipulação',
  dado_sensivel: 'dado sensível',
  fora_escopo: 'fora do escopo',
}

function expected(question: Question): string {
  const risks = Object.entries(question.guardrail)
    .filter(([, flagged]) => flagged)
    .map(([risk]) => RISKS[risk])
  if (risks.length) return `deve ser bloqueada (${risks.join(', ')})`
  return `consulta esperada: ${toolLabel(question.labels.tool)}`
}

function announce(label: string, run: RunViewState): string {
  if (run.status === 'running') {
    const node = currentNode(run)
    return node ? `${label}: ${NODE_LABELS[node]}` : `${label}: iniciada`
  }
  if (run.status === 'finished' && run.action) return `${label}: ${ACTION[run.action].label}`
  return ''
}

interface Props {
  config: GraphConfig
  questionId?: string | null
}

export function Playground({ config, questionId }: Props) {
  const replay = config.mode === 'replay'
  const [view, setView] = useState<View>(
    Object.values(config.providers).includes('both') ? 'compare' : 'single',
  )
  const [questions, setQuestions] = useState<Question[]>([])
  const [selectedId, setSelectedId] = useState<string>(questionId ?? '')
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const single = useRun()
  const jev = useRun()
  const llm = useRun()
  const pipelines = { jev, llm }

  useEffect(() => {
    // O que tem gravação depende do modo e das instruções do LLM: recarrega quando mudam.
    getDataset()
      .then(setQuestions)
      .catch((e: Error) => setError(e.message))
  }, [config.mode, config.llm_prompt_style])

  const examples = questions.filter((q) => q.replayable)
  const selected = questions.find((q) => q.id === selectedId)
  const value = selected ? selected.text : text
  const running =
    view === 'compare'
      ? jev.run.status === 'running' || llm.run.status === 'running'
      : single.run.status === 'running'
  const canRun = !running && (selected ? true : !replay && text.trim() !== '')

  async function execute() {
    if (!canRun) return
    setError(null)
    const body: RunBody = selected ? { question_id: selected.id } : { text }
    try {
      if (view === 'compare') {
        await Promise.all([
          jev.start({ ...body, pipeline: 'jev' }, value),
          llm.start({ ...body, pipeline: 'llm' }, value),
        ])
      } else {
        await single.start(body, value)
      }
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const announcement =
    view === 'compare'
      ? [announce('Jev', jev.run), announce('LLM', llm.run)].filter(Boolean).join('. ')
      : announce('Execução', single.run)

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
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label htmlFor="question" className="text-sm font-medium text-slate-700">
              Pergunte sobre as vendas da Mercado Jornada
            </label>
            <div role="group" aria-label="Visão" className="flex rounded-lg bg-slate-100 p-1">
              {VIEWS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={view === id}
                  onClick={() => setView(id)}
                  className={cx(
                    'rounded-md px-3 py-1 text-sm font-medium',
                    view === id
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
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
            <Button type="submit" disabled={!canRun} loading={running}>
              {running ? 'Executando' : 'Perguntar'}
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
          {replay && questions.length > 0 && examples.length === 0 && (
            <p className="bg-warn-soft rounded-lg px-3 py-2 text-sm text-amber-900">
              Nenhuma pergunta tem gravação para a configuração atual (LLM com system prompt por
              etapa). Volte para "Mesmas perguntas do Jev" na Configuração ou use o modo Live.
            </p>
          )}
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

      {view === 'compare' ? (
        <div className="grid gap-x-6 gap-y-4 md:grid-cols-2">
          {PIPELINES.map(({ id, title, dot, bar }) => (
            <section
              key={id}
              aria-label={title}
              data-testid={`pipeline-${id}`}
              className="grid gap-4 md:row-span-3 md:grid-rows-subgrid"
            >
              <header className={cx('border-l-4 pl-3', bar)}>
                <h2 className="flex items-center gap-2 font-semibold">
                  <span className={cx('size-2.5 rounded-full', dot)} aria-hidden="true" />
                  {title}
                </h2>
                <p className="text-xs text-slate-500">
                  {id === 'jev' ? 'Jev' : 'O LLM'} decide guardrail, triagem e verificação
                  {id === 'llm' &&
                    config.llm_prompt_style === 'native' &&
                    ' com system prompt por etapa'}
                  ; o LLM escreve a resposta.
                </p>
              </header>
              <Card>
                <PipelineTimeline run={pipelines[id].run} thresholds={config.thresholds} compact />
              </Card>
              <AnswerCard run={pipelines[id].run} compact />
            </section>
          ))}
        </div>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
          <Card className="order-2 lg:order-1">
            <CardTitle hint="Cada etapa acende em tempo real. Abra uma etapa para ver o que Jev e LLM responderam.">
              Como o agente chegou lá
            </CardTitle>
            <PipelineTimeline run={single.run} thresholds={config.thresholds} />
          </Card>
          <div className="order-1 lg:sticky lg:top-20 lg:order-2">
            <AnswerCard run={single.run} />
          </div>
        </div>
      )}

      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </div>
  )
}
