// Espelho, escrito à mão, dos modelos do backend (app/config.py, app/graph.py,
// app/providers/base.py, app/dataset.py, app/tools.py). Mudou lá, muda aqui.

export type ProviderName = 'jev' | 'llm'
export type NodeMode = 'llm' | 'jev' | 'both'
export type DecisionNode = 'guardrail' | 'triage' | 'verify'
export type NodeName = 'guardrail' | 'triage' | 'tool' | 'reply' | 'verify' | 'act'
export type Action = 'auto' | 'human' | 'blocked'
export type Mode = 'replay' | 'live'

export interface Thresholds {
  guardrail_block: number
  triage_min_confidence: number
  verify_min_faithful: number
  verify_max_invented: number
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

export interface Tool {
  name: string
  view: string
  title: string
  description: string
}

export interface Question {
  id: string
  text: string
  labels: { tool: string }
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

export interface ToolResult {
  tool: string
  view: string
  columns: string[]
  rows: Record<string, string | number | null>[]
  row_count: number
  truncated: boolean
  latency_ms: number
}

/** O que chega em `tool.finished`: o resultado, ou o erro da consulta. */
export type ToolOutcome = ToolResult | { tool: string; error: string }

export interface RunResult {
  run_id: string
  config_version: string
  mode: Mode
  question_id: string
  question: string
  guardrail: Record<string, Answer> | null
  triage: Record<string, Answer> | null
  tool_result: ToolResult | null
  draft_reply: string | null
  verify: Record<string, Answer> | null
  action: Action
  reason: string | null
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
  | { type: 'tool.finished'; run_id: string; node: 'tool'; data: ToolOutcome }
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

export const isToolError = (outcome: ToolOutcome): outcome is { tool: string; error: string } =>
  'error' in outcome

// Lote (app/metrics/aggregator.py e app/batches.py)

export interface QuestionSummary {
  n: number
  accuracy: number | null
  f1_macro: number | null
}

export interface NodeSummary {
  calls: number
  latency_p50: number | null
  latency_p95: number | null
  tokens_in: number
  tokens_out: number
  cost_total: number
  parse_fail_rate: number
  out_of_schema_rate: number
  latencies: number[]
}

export interface ProviderSummary {
  model: string
  accuracy: number | null
  cost_total: number
  cost_per_1000: number
  latency_p95: number | null
}

export interface QuestionRow {
  question_id: string
  tags: string[]
  action: Action | null
  answers: Record<string, Partial<Record<ProviderName, string | number | null>>>
  labels: Record<string, string | number | boolean>
  disagrees: boolean
  wrong: boolean
  has_error: boolean
}

export interface BatchReport {
  batch_id: string
  config_version: string
  mode: Mode
  llm_model: string
  primary: ProviderName
  n: number
  errors: number
  by_provider: Partial<Record<ProviderName, ProviderSummary>>
  by_node: Record<string, Partial<Record<ProviderName, NodeSummary>>>
  by_question: Record<string, Partial<Record<ProviderName, QuestionSummary>>>
  agreement: Record<string, number>
  questions: QuestionRow[]
}

export interface BatchEstimate {
  n: number
  estimated_cost_usd: number | null
}

export type BatchEvent =
  | { type: 'batch.started'; batch_id: string; data: { n: number } }
  | {
      type: 'batch.progress'
      batch_id: string
      data: {
        done: number
        total: number
        question: { question_id: string; action?: Action; error?: string }
      }
    }
  | { type: 'batch.finished'; batch_id: string; data: BatchReport }
