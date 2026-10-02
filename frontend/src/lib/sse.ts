import { API_URL } from './api'
import type { BatchEvent, RunEvent } from './types'

const RUN_EVENTS = [
  'run.started',
  'node.started',
  'provider.finished',
  'tool.finished',
  'node.finished',
  'run.finished',
] as const

/** Assina os eventos de uma execução. Devolve a função que cancela a assinatura.
 *  `onError` é chamado se a conexão cair antes do `run.finished`. */
export function subscribeRun(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError?: (message: string) => void,
): () => void {
  const source = new EventSource(`${API_URL}/runs/${runId}/events`)
  let finished = false
  const handle = (message: MessageEvent<string>) => {
    const event = JSON.parse(message.data) as RunEvent
    onEvent(event)
    // O servidor fecha o stream depois do run.finished; sem isto o EventSource reconecta.
    if (event.type === 'run.finished') {
      finished = true
      source.close()
    }
  }
  for (const type of RUN_EVENTS) source.addEventListener(type, handle)
  source.onerror = () => {
    if (finished) return
    source.close()
    onError?.('A conexão com o backend caiu durante a execução.')
  }
  return () => source.close()
}

const BATCH_EVENTS = ['batch.started', 'batch.progress', 'batch.finished'] as const

/** Assina o progresso de um lote. Devolve a função que cancela a assinatura. */
export function subscribeBatch(batchId: string, onEvent: (event: BatchEvent) => void): () => void {
  const source = new EventSource(`${API_URL}/batches/${batchId}/events`)
  const handle = (message: MessageEvent<string>) => {
    const event = JSON.parse(message.data) as BatchEvent
    onEvent(event)
    if (event.type === 'batch.finished') source.close()
  }
  for (const type of BATCH_EVENTS) source.addEventListener(type, handle)
  return () => source.close()
}
