import { formatMs, formatPercent, formatTokens, formatUsd } from '../lib/format'
import { QUESTIONS, toolLabel, type QuestionType } from '../lib/questions'
import { isError, type Answer, type DecisionNode, type ProviderOutcome } from '../lib/types'
import { DiffBadge } from './DiffBadge'
import { Badge, cx } from './ui'

const PROVIDER = {
  jev: { label: 'Jev', dot: 'bg-jev', bar: 'bg-jev' },
  llm: { label: 'LLM', dot: 'bg-llm', bar: 'bg-llm' },
}

function formatValue(type: QuestionType, answer: Answer): string {
  if (type === 'noul') return formatPercent(Number(answer.value))
  return toolLabel(String(answer.value))
}

/** Distribuição do Jev entre as opções: as três maiores, com rótulo e valor visíveis. */
function Probabilities({ answer, bar }: { answer: Answer; bar: string }) {
  if (!answer.probabilities) return null
  const top = Object.entries(answer.probabilities)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3)
  return (
    <ul className="mt-2 flex flex-col gap-1" aria-label="Probabilidade por opção">
      {top.map(([label, p]) => (
        <li key={label} className="grid grid-cols-[8rem_1fr_2.5rem] items-center gap-2 text-xs">
          <span className="truncate text-slate-600">{toolLabel(label)}</span>
          <span className="h-1.5 overflow-hidden rounded-full bg-slate-100">
            <span className={cx('block h-full', bar)} style={{ width: `${p * 100}%` }} />
          </span>
          <span className="text-right text-slate-500 tabular-nums">{formatPercent(p)}</span>
        </li>
      ))}
    </ul>
  )
}

interface Props {
  node: DecisionNode | 'reply'
  outcome: ProviderOutcome
  disagreements: Set<string>
}

export function ProviderCard({ node, outcome, disagreements }: Props) {
  const provider = PROVIDER[outcome.provider]
  const header = (
    <div className="flex items-center justify-between gap-2">
      <h3 className="flex items-center gap-2 font-semibold">
        <span className={cx('size-2.5 rounded-full', provider.dot)} aria-hidden="true" />
        {provider.label}
        {!isError(outcome) && (
          <span className="text-xs font-normal text-slate-500">{outcome.model}</span>
        )}
      </h3>
      <span className="flex gap-1">
        {!isError(outcome) && outcome.raw.prompt_style === 'native' && (
          <Badge tone="llm">system prompt</Badge>
        )}
        {outcome.is_primary && <Badge tone="brand">primário</Badge>}
      </span>
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
          <dd className="font-semibold tabular-nums">{formatMs(outcome.latency_ms)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Tokens</dt>
          <dd className="tabular-nums">
            {formatTokens(outcome.tokens_in)} / {formatTokens(outcome.tokens_out)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Custo</dt>
          <dd className="whitespace-nowrap tabular-nums">{formatUsd(outcome.cost_usd)}</dd>
        </div>
      </dl>

      {(!outcome.parse_ok || !outcome.values_in_schema) && (
        <div className="flex flex-wrap gap-1">
          {!outcome.parse_ok && <Badge tone="danger">JSON inválido</Badge>}
          {outcome.parse_ok && !outcome.values_in_schema && (
            <Badge tone="danger">valor fora das opções</Badge>
          )}
        </div>
      )}

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
                className={cx(
                  'rounded-md px-2 py-1.5',
                  differs ? 'bg-warn-soft ring-1 ring-amber-300' : 'bg-slate-50',
                )}
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
                    <Probabilities answer={answer} bar={provider.bar} />
                  </>
                ) : (
                  <span className="text-slate-500">sem resposta</span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </article>
  )
}
