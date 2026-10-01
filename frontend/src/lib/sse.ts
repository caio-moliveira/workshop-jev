import { API_URL } from './api'
import type { RunEvent } from './types'

const RUN_EVENTS = [
  'run.started',
  'node.started',
  'provider.finished',
  'node.finished',
  'run.finished',
] as const

/** Assina os eventos de uma execução. Devolve a função que cancela a assinatura. */
export function subscribeRun(runId: string, onEvent: (event: RunEvent) => void): () => void {
  const source = new EventSource(`${API_URL}/runs/${runId}/events`)
  const handle = (message: MessageEvent<string>) => {
    const event = JSON.parse(message.data) as RunEvent
    onEvent(event)
    // O servidor fecha o stream depois do run.finished; sem isto o EventSource reconecta.
    if (event.type === 'run.finished') source.close()
  }
  for (const type of RUN_EVENTS) source.addEventListener(type, handle)
  return () => source.close()
}
