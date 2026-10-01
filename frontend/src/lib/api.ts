import type { GraphConfig, Pricing, RunResult, Ticket } from './types'

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
  return request<Ticket[]>(`/dataset?${query}`)
}

export const postRun = (body: { ticket_id: string } | { text: string }) =>
  request<{ run_id: string }>('/runs', {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const getRun = (runId: string) => request<RunResult>(`/runs/${runId}`)
