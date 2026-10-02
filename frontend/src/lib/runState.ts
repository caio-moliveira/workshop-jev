import type {
  Action,
  Answer,
  DecisionNode,
  NodeName,
  ProviderOutcome,
  RunEvent,
  RunResult,
  ToolOutcome,
} from './types'

export type NodeStatus = 'waiting' | 'running' | 'done' | 'skipped' | 'blocked'

export interface RunViewState {
  runId: string | null
  status: 'idle' | 'running' | 'finished' | 'failed'
  question: string | null
  nodes: Record<NodeName, NodeStatus>
  outcomes: Record<NodeName, ProviderOutcome[]>
  /** Respostas do primário em cada node de decisão, como vieram em `node.finished`. */
  answers: Partial<Record<DecisionNode, Record<string, Answer> | null>>
  tool: ToolOutcome | null
  path: NodeName[]
  action: Action | null
  reason: string | null
  draftReply: string | null
  result: RunResult | null
  error: string | null
}

export const NODES: NodeName[] = ['guardrail', 'triage', 'tool', 'reply', 'verify', 'act']

const byNode = <T>(value: () => T) =>
  Object.fromEntries(NODES.map((n) => [n, value()])) as Record<NodeName, T>

export const initialRunState = (runId: string | null = null): RunViewState => ({
  runId,
  status: runId ? 'running' : 'idle',
  question: null,
  nodes: byNode<NodeStatus>(() => 'waiting'),
  outcomes: byNode<ProviderOutcome[]>(() => []),
  answers: {},
  tool: null,
  path: [],
  action: null,
  reason: null,
  draftReply: null,
  result: null,
  error: null,
})

/** A conexão caiu antes do fim: a execução não fica presa em "rodando". */
export const failRun = (state: RunViewState, error: string): RunViewState =>
  state.status === 'running' ? { ...state, status: 'failed', error } : state

/** Transforma a sequência de eventos SSE no estado da tela. Função pura. */
export function reduceRun(state: RunViewState, event: RunEvent): RunViewState {
  switch (event.type) {
    case 'run.started': {
      const question = event.data.question
      return {
        ...initialRunState(event.run_id),
        question: typeof question === 'string' ? question : state.question,
      }
    }
    case 'node.started':
      return {
        ...state,
        nodes: { ...state.nodes, [event.node]: 'running' },
        path: [...state.path, event.node],
      }
    case 'provider.finished':
      return {
        ...state,
        outcomes: {
          ...state.outcomes,
          [event.node]: [...state.outcomes[event.node], event.data],
        },
      }
    case 'tool.finished':
      return { ...state, tool: event.data }
    case 'node.finished': {
      const { draft_reply: draft, answers, action, reason } = event.data
      const next = { ...state, nodes: { ...state.nodes, [event.node]: 'done' as const } }
      if (typeof draft === 'string') next.draftReply = draft
      if ('answers' in event.data) {
        next.answers = {
          ...state.answers,
          [event.node]: (answers as Record<string, Answer> | null) ?? null,
        }
      }
      if (typeof action === 'string') next.action = action as Action
      if (typeof reason === 'string') next.reason = reason
      return next
    }
    case 'run.finished': {
      const result = event.data
      const nodes = byNode<NodeStatus>(() => 'skipped')
      for (const node of result.path) nodes[node] = 'done'
      if (result.action === 'blocked') nodes.guardrail = 'blocked'
      return {
        ...state,
        status: 'finished',
        question: result.question,
        nodes,
        path: result.path,
        action: result.action,
        reason: result.reason,
        draftReply: result.draft_reply,
        tool: result.tool_result ?? state.tool,
        answers: {
          guardrail: result.guardrail,
          triage: result.triage,
          verify: result.verify,
        },
        result,
      }
    }
  }
}

/** A etapa em andamento, para anunciar ao leitor de tela. */
export const currentNode = (state: RunViewState): NodeName | null =>
  NODES.find((node) => state.nodes[node] === 'running') ?? null
