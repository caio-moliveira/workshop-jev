// Espelho, escrito à mão, dos modelos do backend (app/config.py, app/graph.py,
// app/providers/base.py, app/dataset.py). Mudou lá, muda aqui.

export type ProviderName = 'jev' | 'llm'
export type NodeMode = 'llm' | 'jev' | 'both'
export type DecisionNode = 'guardrail' | 'triage' | 'verify'
export type NodeName = DecisionNode | 'reply' | 'act'
export type Action = 'auto' | 'human' | 'blocked'
export type Mode = 'replay' | 'live'

export interface Thresholds {
  guardrail_block: number
  triage_min_confidence: number
  verify_min_policy: number
  verify_max_overpromise: number
}

export interface CatalogModel {
  label: string
  provider: 'openai' | 'anthropic'
  model_id: string
}

export interface GraphConfig {
  config_version: string
  mode: Mode
  primary: ProviderName
  llm_model: string
  providers: Record<DecisionNode, NodeMode>
  llm_model_overrides: Partial<Record<DecisionNode, string>>
  thresholds: Thresholds
  catalog: CatalogModel[]
}

export interface ModelPrice {
  input: number | null
  output: number | null
}

export interface Pricing {
  reference_date: string
  source: string
  models: Record<string, ModelPrice>
}

export interface Ticket {
  id: string
  text: string
  channel: 'email' | 'chat' | 'formulario'
  labels: {
    fila: string
    urgencia: number
    pede_reembolso: boolean
    risco_churn: boolean
  }
  guardrail: {
    injection: boolean
    dado_sensivel: boolean
    fora_escopo: boolean
  }
  tags: string[]
  difficulty: 'easy' | 'medium' | 'hard'
  replayable: boolean
}

export interface Answer {
  value: string | number
  confidence: number | null
  probabilities: Record<string, number> | null
}

export interface NodeMetric {
  provider: ProviderName
  model: string
  answers: Record<string, Answer>
  latency_ms: number
  tokens_in: number
  tokens_out: number
  cost_usd: number
  parse_ok: boolean
  values_in_schema: boolean
  raw: Record<string, unknown>
  node: NodeName
  is_primary: boolean
}

/** O que chega em `provider.finished`: a métrica, ou o erro do provider. */
export type ProviderOutcome =
  NodeMetric | { provider: ProviderName; is_primary?: boolean; error: string }

export interface RunResult {
  run_id: string
  config_version: string
  mode: Mode
  ticket_id: string
  guardrail: Record<string, Answer> | null
  triage: Record<string, Answer> | null
  draft_reply: string | null
  verify: Record<string, Answer> | null
  action: Action
  path: NodeName[]
  metrics: NodeMetric[]
  errors: string[]
}

export type RunEvent =
  | {
      type: 'run.started'
      run_id: string
      node: null
      data: Record<string, unknown>
    }
  | {
      type: 'node.started'
      run_id: string
      node: NodeName
      data: Record<string, unknown>
    }
  | {
      type: 'provider.finished'
      run_id: string
      node: NodeName
      data: ProviderOutcome
    }
  | {
      type: 'node.finished'
      run_id: string
      node: NodeName
      data: Record<string, unknown>
    }
  | { type: 'run.finished'; run_id: string; node: null; data: RunResult }

export const isError = (
  outcome: ProviderOutcome,
): outcome is { provider: ProviderName; is_primary?: boolean; error: string } => 'error' in outcome
