import { useEffect, useState } from 'react'

import { getConfig, getPricing } from './lib/api'
import type { GraphConfig, Pricing } from './lib/types'
import { Batch } from './pages/Batch'
import { Config } from './pages/Config'
import { Playground } from './pages/Playground'

type Tab = 'config' | 'playground' | 'batch'

const TABS: { id: Tab; label: string }[] = [
  { id: 'config', label: 'Configuração' },
  { id: 'playground', label: 'Playground' },
  { id: 'batch', label: 'Lote' },
]

function App() {
  const [tab, setTab] = useState<Tab>('playground')
  const [config, setConfig] = useState<GraphConfig | null>(null)
  const [pricing, setPricing] = useState<Pricing | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openTicket, setOpenTicket] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getConfig(), getPricing()])
      .then(([config, pricing]) => {
        setConfig(config)
        setPricing(pricing)
      })
      .catch(() => setError('Backend fora do ar. Rode: cd backend && uv run uvicorn app.main:app'))
  }, [])

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <h1 className="text-lg font-semibold">JEV Jornada</h1>
          <nav className="flex gap-1">
            {TABS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`rounded px-3 py-1.5 text-sm ${
                  tab === id ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
          {config && (
            <span
              className={`ml-auto rounded px-2 py-0.5 text-xs font-semibold uppercase ${
                config.mode === 'replay'
                  ? 'bg-slate-200 text-slate-700'
                  : 'bg-emerald-100 text-emerald-800'
              }`}
            >
              {config.mode}
            </span>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        {error && <p className="text-red-700">{error}</p>}
        {config && tab === 'config' && (
          <Config config={config} pricing={pricing} onSaved={setConfig} />
        )}
        {/* Playground e Lote ficam montados: trocar de aba não perde a execução nem o relatório. */}
        {config && (
          <div hidden={tab !== 'playground'}>
            <Playground key={openTicket ?? ''} config={config} ticketId={openTicket} />
          </div>
        )}
        {config && (
          <div hidden={tab !== 'batch'}>
            <Batch
              config={config}
              onOpenTicket={(ticketId) => {
                setOpenTicket(ticketId)
                setTab('playground')
              }}
            />
          </div>
        )}
      </main>
    </div>
  )
}

export default App
