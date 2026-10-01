import type { Action, NodeName, ProviderOutcome, RunEvent, RunResult } from './types'

export type NodeStatus = 'waiting' | 'running' | 'done' | 'skipped' | 'blocked'

export interface RunViewState {
  runId: string | null
  status: 'idle' | 'running' | 'finished'
  nodes: Record<NodeName, NodeStatus>
  outcomes: Record<NodeName, ProviderOutcome[]>
  path: NodeName[]
  action: Action | null
  draftReply: string | null
  result: RunResult | null
}

export const NODES: NodeName[] = ['guardrail', 'triage', 'reply', 'verify', 'act']

const byNode = <T>(value: () => T) =>
  Object.fromEntries(NODES.map((n) => [n, value()])) as Record<NodeName, T>

export const initialRunState = (runId: string | null = null): RunViewState => ({
  runId,
  status: runId ? 'running' : 'idle',
  nodes: byNode<NodeStatus>(() => 'waiting'),
  outcomes: byNode<ProviderOutcome[]>(() => []),
  path: [],
  action: null,
  draftReply: null,
  result: null,
})

/** Transforma a sequência de eventos SSE no estado da tela. Função pura. */
export function reduceRun(state: RunViewState, event: RunEvent): RunViewState {
  switch (event.type) {
    case 'run.started':
      return initialRunState(event.run_id)
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
    case 'node.finished': {
      const draft = event.data.draft_reply
      return {
        ...state,
        nodes: { ...state.nodes, [event.node]: 'done' },
        draftReply: typeof draft === 'string' ? draft : state.draftReply,
      }
    }
    case 'run.finished': {
      const result = event.data
      const nodes = byNode<NodeStatus>(() => 'skipped')
      for (const node of result.path) nodes[node] = 'done'
      if (result.action === 'blocked') nodes.guardrail = 'blocked'
      return {
        ...state,
        status: 'finished',
        nodes,
        path: result.path,
        action: result.action,
        draftReply: result.draft_reply,
        result,
      }
    }
  }
}

/** Ids das arestas percorridas, no formato `origem-destino`. */
export const takenEdges = (path: NodeName[]): string[] =>
  path.slice(1).map((node, i) => `${path[i]}-${node}`)
