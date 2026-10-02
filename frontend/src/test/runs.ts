// Execuções de exemplo para os testes: sequências de eventos SSE como o backend emite.
import { initialRunState, reduceRun } from '../lib/runState'
import type {
  Answer,
  NodeMetric,
  NodeName,
  ProviderName,
  RunEvent,
  RunResult,
  Thresholds,
  ToolResult,
} from '../lib/types'

export const RUN = 'r1'

export const THRESHOLDS: Thresholds = {
  guardrail_block: 0.7,
  triage_min_confidence: 0.8,
  verify_min_faithful: 0.8,
  verify_max_invented: 0.3,
}

export const answer = (value: string | number, confidence: number | null = null): Answer => ({
  value,
  confidence,
  probabilities: null,
})

export const SAFE = {
  injection: answer(0.01),
  dado_sensivel: answer(0.02),
  fora_escopo: answer(0.03),
}
export const TRIAGE = { tool: answer('vendas_mensal', 0.94) }
export const VERIFY = {
  fiel_aos_dados: answer(0.96),
  responde_pergunta: answer(0.97),
  inventa_numero: answer(0.04),
}

export const TOOL: ToolResult = {
  tool: 'vendas_mensal',
  view: 'vw_vendas_mensal',
  columns: ['mes', 'receita'],
  rows: [
    { mes: '2026-08', receita: 470878.15 },
    { mes: '2026-09', receita: 578064.86 },
  ],
  row_count: 2,
  truncated: false,
  latency_ms: 12,
}

export const metric = (
  node: NodeName,
  provider: ProviderName,
  answers: Record<string, Answer> = {},
  latency = provider === 'jev' ? 40 : 1200,
): NodeMetric => ({
  provider,
  model: provider === 'jev' ? 'jev-1.13.0' : 'gpt-5.6-luna',
  answers,
  latency_ms: latency,
  tokens_in: 100,
  tokens_out: 5,
  cost_usd: 0.001,
  parse_ok: true,
  values_in_schema: true,
  raw: {},
  node,
  is_primary: provider === 'jev',
})

export function decision(
  node: 'guardrail' | 'triage' | 'verify',
  answers: Record<string, Answer>,
  llmAnswers = answers,
): RunEvent[] {
  return [
    { type: 'node.started', run_id: RUN, node, data: {} },
    { type: 'provider.finished', run_id: RUN, node, data: metric(node, 'jev', answers) },
    { type: 'provider.finished', run_id: RUN, node, data: metric(node, 'llm', llmAnswers) },
    { type: 'node.finished', run_id: RUN, node, data: { primary: 'jev', answers } },
  ]
}

export const result = (changes: Partial<RunResult> = {}): RunResult => ({
  run_id: RUN,
  config_version: '2',
  mode: 'replay',
  question_id: 'q-001',
  question: 'Como foi a receita mês a mês em 2026?',
  guardrail: SAFE,
  triage: TRIAGE,
  tool_result: TOOL,
  draft_reply: 'Em setembro a receita foi de R$ 578.064,86.',
  verify: VERIFY,
  action: 'auto',
  reason: null,
  path: ['guardrail', 'triage', 'tool', 'reply', 'verify', 'act'],
  metrics: [],
  errors: [],
  ...changes,
})

const started: RunEvent = {
  type: 'run.started',
  run_id: RUN,
  node: null,
  data: { question: 'Como foi a receita mês a mês em 2026?' },
}

export const HAPPY: RunEvent[] = [
  started,
  ...decision('guardrail', SAFE),
  ...decision('triage', TRIAGE),
  { type: 'node.started', run_id: RUN, node: 'tool', data: {} },
  { type: 'tool.finished', run_id: RUN, node: 'tool', data: TOOL },
  { type: 'node.finished', run_id: RUN, node: 'tool', data: { tool: 'vendas_mensal', ok: true } },
  { type: 'node.started', run_id: RUN, node: 'reply', data: {} },
  { type: 'provider.finished', run_id: RUN, node: 'reply', data: metric('reply', 'llm', {}, 2850) },
  {
    type: 'node.finished',
    run_id: RUN,
    node: 'reply',
    data: { draft_reply: 'Em setembro a receita foi de R$ 578.064,86.' },
  },
  ...decision('verify', VERIFY),
  { type: 'node.started', run_id: RUN, node: 'act', data: {} },
  { type: 'node.finished', run_id: RUN, node: 'act', data: { action: 'auto', reason: null } },
  { type: 'run.finished', run_id: RUN, node: null, data: result() },
]

const BLOCKED_GUARDRAIL = { ...SAFE, injection: answer(0.97) }
const BLOCKED_REASON = 'tentativa de manipular o assistente'

export const BLOCKED: RunEvent[] = [
  started,
  ...decision('guardrail', BLOCKED_GUARDRAIL),
  {
    type: 'run.finished',
    run_id: RUN,
    node: null,
    data: result({
      guardrail: BLOCKED_GUARDRAIL,
      triage: null,
      tool_result: null,
      draft_reply: null,
      verify: null,
      action: 'blocked',
      reason: BLOCKED_REASON,
      path: ['guardrail'],
    }),
  },
]

export const replay = (events: RunEvent[]) => events.reduce(reduceRun, initialRunState())
