import { formatMs, formatPercent, formatTokens, formatUsd } from '../lib/format'
import { QUESTIONS, URGENCY_LABELS, type QuestionType } from '../lib/questions'
import { isError, type Answer, type DecisionNode, type ProviderOutcome } from '../lib/types'
import { DiffBadge } from './DiffBadge'

const PROVIDER_LABEL = { jev: 'Jev', llm: 'LLM' }

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-medium ${
        ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-100 text-red-700'
      }`}
    >
      {label}
    </span>
  )
}

function formatValue(type: QuestionType, answer: Answer): string {
  if (type === 'score') return URGENCY_LABELS[Number(answer.value)] ?? String(answer.value)
  if (type === 'noul') return formatPercent(Number(answer.value))
  return String(answer.value)
}

function Probabilities({ type, answer }: { type: QuestionType; answer: Answer }) {
  if (!answer.probabilities) return null
  return (
    <div className="mt-1 flex h-1.5 overflow-hidden rounded bg-slate-100">
      {Object.entries(answer.probabilities).map(([label, p], i) => (
        <div
          key={label}
          title={`${type === 'score' ? URGENCY_LABELS[Number(label)] : label}: ${formatPercent(p)}`}
          className={i % 2 ? 'bg-indigo-300' : 'bg-indigo-500'}
          style={{ width: `${p * 100}%` }}
        />
      ))}
    </div>
  )
}

interface Props {
  node: DecisionNode | 'reply'
  outcome: ProviderOutcome
  disagreements: Set<string>
}

export function ProviderCard({ node, outcome, disagreements }: Props) {
  const header = (
    <div className="flex items-center justify-between gap-2">
      <h3 className="font-semibold">
        {PROVIDER_LABEL[outcome.provider]}
        {!isError(outcome) && (
          <span className="ml-2 text-xs font-normal text-slate-500">{outcome.model}</span>
        )}
      </h3>
      {outcome.is_primary && (
        <span className="rounded bg-indigo-600 px-1.5 py-0.5 text-xs font-medium text-white">
          primário
        </span>
      )}
    </div>
  )

  if (isError(outcome)) {
    return (
      <article className="rounded-lg border border-red-200 bg-white p-4">
        {header}
        <p className="mt-3 text-sm text-red-700">Falhou: {outcome.error}</p>
      </article>
    )
  }

  const questions = node === 'reply' ? [] : QUESTIONS[node]
  return (
    <article className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4">
      {header}

      <dl className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-xs text-slate-500">Latência</dt>
          <dd className="font-semibold">{formatMs(outcome.latency_ms)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Tokens</dt>
          <dd>
            {formatTokens(outcome.tokens_in)} / {formatTokens(outcome.tokens_out)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Custo</dt>
          <dd>{formatUsd(outcome.cost_usd)}</dd>
        </div>
      </dl>

      <div className="flex flex-wrap gap-1">
        <Badge ok={outcome.parse_ok} label={outcome.parse_ok ? 'JSON válido' : 'JSON inválido'} />
        <Badge
          ok={outcome.values_in_schema}
          label={outcome.values_in_schema ? 'valores nas opções' : 'valor fora das opções'}
        />
      </div>

      {questions.length > 0 && (
        <ul className="flex flex-col gap-2 text-sm">
          {questions.map((question) => {
            const answer = outcome.answers[question.name]
            const differs = disagreements.has(question.name)
            return (
              <li
                key={question.name}
                data-testid={`answer-${question.name}`}
                data-disagrees={differs}
                className={`rounded px-2 py-1 ${differs ? 'bg-amber-50 ring-1 ring-amber-300' : ''}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-slate-600">{question.label}</span>
                  {differs && <DiffBadge />}
                </div>
                {answer ? (
                  <>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-medium">{formatValue(question.type, answer)}</span>
                      {answer.confidence !== null && (
                        <span className="text-xs text-slate-500">
                          confiança {formatPercent(answer.confidence)}
                        </span>
                      )}
                    </div>
                    <Probabilities type={question.type} answer={answer} />
                  </>
                ) : (
                  <span className="text-slate-400">sem resposta</span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </article>
  )
}
