import { useEffect, useState } from 'react'

import { Card, Skeleton, Tabs, cx } from './components/ui'
import { getConfig, getPricing } from './lib/api'
import type { GraphConfig, Pricing } from './lib/types'
import { Batch } from './pages/Batch'
import { Config } from './pages/Config'
import { Playground } from './pages/Playground'

type Tab = 'playground' | 'batch' | 'config'

const TABS: { id: Tab; label: string }[] = [
  { id: 'playground', label: 'Playground' },
  { id: 'batch', label: 'Lote' },
  { id: 'config', label: 'Configuração' },
]

const MODE = {
  replay: {
    label: 'Replay',
    hint: 'Respostas gravadas: sem chaves e sem banco',
    style: 'bg-slate-100 text-slate-700',
    dot: 'bg-slate-400',
  },
  live: {
    label: 'Live',
    hint: 'Chama Jev, LLM e o banco de verdade',
    style: 'bg-ok-soft text-emerald-800',
    dot: 'bg-ok',
  },
}

function App() {
  const [tab, setTab] = useState<Tab>('playground')
  const [config, setConfig] = useState<GraphConfig | null>(null)
  const [pricing, setPricing] = useState<Pricing | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openQuestion, setOpenQuestion] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getConfig(), getPricing()])
      .then(([config, pricing]) => {
        setConfig(config)
        setPricing(pricing)
      })
      .catch(() => setError('cd backend && uv run uvicorn app.main:app --reload'))
  }, [])

  const panel = (id: Tab) => ({
    role: 'tabpanel',
    id: `app-panel-${id}`,
    'aria-labelledby': `app-tab-${id}`,
    hidden: tab !== id,
  })

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="bg-brand-600 flex size-8 items-center justify-center rounded-lg text-sm font-bold text-white"
            >
              J
            </span>
            <div className="leading-tight">
              <h1 className="font-semibold">JEV Jornada</h1>
              <p className="text-xs text-slate-500">Agente de vendas · Jev × LLM</p>
            </div>
          </div>
          <Tabs items={TABS} value={tab} onChange={setTab} label="Seções" idPrefix="app" />
          {config && (
            <span
              className={cx(
                'ml-auto inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium',
                MODE[config.mode].style,
              )}
              title={MODE[config.mode].hint}
            >
              <span className={cx('size-2 rounded-full', MODE[config.mode].dot)} />
              {MODE[config.mode].label}
              <span className="hidden font-normal sm:inline">· {MODE[config.mode].hint}</span>
            </span>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        {error && (
          <Card className="border-red-200" role="alert">
            <p className="font-medium text-red-800">Não foi possível falar com o backend.</p>
            <p className="mt-1 text-sm text-red-700">
              Suba a API e recarregue a página:{' '}
              <code className="rounded bg-red-50 px-1.5 py-0.5 font-mono">{error}</code>
            </p>
          </Card>
        )}
        {!config && !error && (
          <div className="flex flex-col gap-4" aria-busy="true" aria-label="Carregando">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-72 w-full" />
          </div>
        )}
        {config && (
          <>
            {/* Playground e Lote ficam montados: trocar de aba não perde a execução nem o relatório. */}
            <div {...panel('playground')}>
              <Playground key={openQuestion ?? ''} config={config} questionId={openQuestion} />
            </div>
            <div {...panel('batch')}>
              <Batch
                config={config}
                onOpenQuestion={(questionId) => {
                  setOpenQuestion(questionId)
                  setTab('playground')
                }}
              />
            </div>
            <div {...panel('config')}>
              {tab === 'config' && <Config config={config} pricing={pricing} onSaved={setConfig} />}
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export default App
