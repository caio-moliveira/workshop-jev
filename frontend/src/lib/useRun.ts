import { useCallback, useEffect, useReducer, useRef } from 'react'

import { postRun, type RunBody } from './api'
import { initialRunState, runReducer } from './runState'
import { subscribeRun } from './sse'

/** Uma execução acompanhada pela tela: dispara POST /runs e segue os eventos SSE.
 *  A visão lado a lado usa duas instâncias, uma por provider. */
export function useRun() {
  const [run, dispatch] = useReducer(runReducer, initialRunState())
  const unsubscribe = useRef<(() => void) | null>(null)

  useEffect(() => () => unsubscribe.current?.(), [])

  const start = useCallback(async (body: RunBody, question: string) => {
    unsubscribe.current?.()
    const { run_id } = await postRun(body)
    dispatch({ type: 'run.started', run_id, node: null, data: { question } })
    unsubscribe.current = subscribeRun(run_id, dispatch, (error) =>
      dispatch({ type: 'failed', error }),
    )
  }, [])

  return { run, start }
}
