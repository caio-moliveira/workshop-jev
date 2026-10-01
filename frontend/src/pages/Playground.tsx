import { useEffect, useReducer, useRef, useState } from 'react'

import { FlowGraph } from '../components/FlowGraph'
import { ProviderCard } from '../components/ProviderCard'
import { getDataset, postRun } from '../lib/api'
import { disagreements } from '../lib/diff'
import { NODE_LABELS, isDecisionNode } from '../lib/questions'
import { initialRunState, reduceRun } from '../lib/runState'
import { subscribeRun } from '../lib/sse'
import type { Action, GraphConfig, NodeName, Ticket } from '../lib/types'

const ACTION_LABEL: Record<Action, string> = {
  auto: 'Ação automática',
  human: 'Revisão humana',
  blocked: 'Bloqueado no guardrail',
}

const ACTION_STYLE: Record<Action, string> = {
  auto: 'bg-emerald-100 text-emerald-800',
  human: 'bg-amber-100 text-amber-800',
  blocked: 'bg-red-100 text-red-800',
}

interface Props {
  config: GraphConfig
  ticketId?: string | null
}

export function Playground({ config, ticketId }: Props) {
  const replay = config.mode === 'replay'
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedTicket, setSelectedTicket] = useState<string>(ticketId ?? '')
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<NodeName | null>('triage')
  const [run, dispatch] = useReducer(reduceRun, initialRunState())
  const unsubscribe = useRef<(() => void) | null>(null)

  useEffect(() => {
    getDataset()
      .then(setTickets)
      .catch((e: Error) => setError(e.message))
    return () => unsubscribe.current?.()
  }, [])

  const options = replay ? tickets.filter((t) => t.replayable) : tickets
  const ticket = tickets.find((t) => t.id === selectedTicket)

  async function execute() {
    setError(null)
    unsubscribe.current?.()
    try {
      const body = selectedTicket ? { ticket_id: selectedTicket } : { text }
      const { run_id } = await postRun(body)
      dispatch({ type: 'run.started', run_id, node: null, data: {} })
      unsubscribe.current = subscribeRun(run_id, dispatch)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const outcomes = selectedNode ? run.outcomes[selectedNode] : []
  const diffs =
    selectedNode && isDecisionNode(selectedNode)
      ? disagreements(selectedNode, outcomes)
      : new Set<string>()

  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center gap-3">
          <select
            className="min-w-72 rounded border border-slate-300 px-2 py-1"
            value={selectedTicket}
            onChange={(e) => setSelectedTicket(e.target.value)}
          >
            <option value="">{replay ? 'Escolha um ticket' : 'Ticket digitado'}</option>
            {options.map((t) => (
              <option key={t.id} value={t.id}>
                {t.id} · {t.tags.join(', ')}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={execute}
            disabled={run.status === 'running' || (!selectedTicket && (replay || !text.trim()))}
            className="rounded bg-indigo-600 px-4 py-1.5 font-medium text-white disabled:opacity-40"
          >
            {run.status === 'running' ? 'Executando…' : 'Executar'}
          </button>
        </div>
        <textarea
          rows={3}
          disabled={replay || Boolean(selectedTicket)}
          value={ticket ? ticket.text : text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            replay
              ? 'Em modo replay só rodam os tickets do golden set que têm gravação.'
              : 'Digite um ticket ou escolha um do golden set.'
          }
          className="rounded border border-slate-300 p-2 text-sm disabled:bg-slate-50"
        />
        {ticket && (
          <p className="text-xs text-slate-500">
            Gabarito: fila {ticket.labels.fila} · urgência {ticket.labels.urgencia} · reembolso{' '}
            {ticket.labels.pede_reembolso ? 'sim' : 'não'} · churn{' '}
            {ticket.labels.risco_churn ? 'sim' : 'não'}
          </p>
        )}
        {error && <p className="text-sm text-red-700">{error}</p>}
      </section>

      <FlowGraph
        statuses={run.nodes}
        path={run.path}
        selected={selectedNode}
        onSelect={setSelectedNode}
      />

      {run.action && (
        <div className="flex flex-wrap items-center gap-3">
          <span className={`rounded px-3 py-1 font-semibold ${ACTION_STYLE[run.action]}`}>
            {ACTION_LABEL[run.action]}
          </span>
          <span className="text-sm text-slate-500">
            Caminho: {run.path.map((n) => NODE_LABELS[n]).join(' → ')}
          </span>
        </div>
      )}

      {selectedNode && (
        <section>
          <h2 className="mb-2 font-semibold">{NODE_LABELS[selectedNode]}</h2>
          {outcomes.length === 0 ? (
            <p className="text-sm text-slate-500">
              {selectedNode === 'act'
                ? 'Node determinístico, sem provider.'
                : 'Sem resultados ainda.'}
            </p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {outcomes.map((outcome) => (
                <ProviderCard
                  key={outcome.provider}
                  node={isDecisionNode(selectedNode) ? selectedNode : 'reply'}
                  outcome={outcome}
                  disagreements={diffs}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {run.draftReply && (
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-2 font-semibold">Rascunho de resposta</h2>
          <p className="text-sm whitespace-pre-wrap text-slate-700">{run.draftReply}</p>
        </section>
      )}

      {run.result && run.result.errors.length > 0 && (
        <section className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {run.result.errors.map((e) => (
            <p key={e}>{e}</p>
          ))}
        </section>
      )}
    </div>
  )
}
