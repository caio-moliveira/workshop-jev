import type {
  BatchEstimate,
  BatchReport,
  GraphConfig,
  Pricing,
  Question,
  RunResult,
  Tool,
} from './types'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : response.statusText
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export const getConfig = () => request<GraphConfig>('/config')

export const putConfig = (config: GraphConfig) =>
  request<GraphConfig>('/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  })

export const getPricing = () => request<Pricing>('/pricing')

export function getDataset(params: { tag?: string; limit?: number } = {}) {
  const query = new URLSearchParams()
  if (params.tag) query.set('tag', params.tag)
  if (params.limit) query.set('limit', String(params.limit))
  return request<Question[]>(`/dataset?${query}`)
}

export const getTools = () => request<Tool[]>('/tools')

export const getPrompts = () => request<Record<string, string>>('/prompts')

export type RunBody = ({ question_id: string } | { text: string }) & {
  pipeline?: 'jev' | 'llm'
}

export const postRun = (body: RunBody) =>
  request<{ run_id: string }>('/runs', {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const getRun = (runId: string) => request<RunResult>(`/runs/${runId}`)

const batchQuery = (n: number, tag?: string) =>
  new URLSearchParams({ n: String(n), ...(tag ? { tag } : {}) })

export const getBatchEstimate = (n: number, tag?: string) =>
  request<BatchEstimate>(`/batches/estimate?${batchQuery(n, tag)}`)

export const postBatch = (n: number, tag?: string) =>
  request<BatchEstimate & { batch_id: string }>('/batches', {
    method: 'POST',
    body: JSON.stringify({ n, tag: tag || null }),
  })

export const getBatchReport = (batchId: string) =>
  request<BatchReport>(`/batches/${batchId}/report`)

export const exportUrl = (batchId: string, format: 'csv' | 'json') =>
  `${API_URL}/batches/${batchId}/export?format=${format}`
