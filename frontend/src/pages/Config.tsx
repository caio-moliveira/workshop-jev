import { useState } from 'react'

import { putConfig } from '../lib/api'
import { formatPrice } from '../lib/format'
import { DECISION_NODES, NODE_LABELS } from '../lib/questions'
import type { GraphConfig, NodeMode, Pricing, Thresholds } from '../lib/types'

const MODES: { value: NodeMode; label: string }[] = [
  { value: 'llm', label: 'LLM' },
  { value: 'jev', label: 'Jev' },
  { value: 'both', label: 'Ambos' },
]

const THRESHOLDS: { key: keyof Thresholds; label: string }[] = [
  { key: 'guardrail_block', label: 'Guardrail bloqueia com risco ≥' },
  {
    key: 'triage_min_confidence',
    label: 'Triagem vai para humano com confiança da fila <',
  },
  {
    key: 'verify_min_policy',
    label: 'Verificação vai para humano se segue a política <',
  },
  {
    key: 'verify_max_overpromise',
    label: 'Verificação vai para humano se promete fora ≥',
  },
]

const PROVIDER_GROUPS = { openai: 'OpenAI', anthropic: 'Anthropic' }

interface Props {
  config: GraphConfig
  pricing: Pricing | null
  onSaved: (config: GraphConfig) => void
}

export function Config({ config, pricing, onSaved }: Props) {
  const [draft, setDraft] = useState(config)
  const [message, setMessage] = useState<string | null>(null)
  const dirty = JSON.stringify(draft) !== JSON.stringify(config)

  const update = (changes: Partial<GraphConfig>) => setDraft({ ...draft, ...changes })

  async function save() {
    try {
      const saved = await putConfig(draft)
      setDraft(saved)
      onSaved(saved)
      setMessage('Configuração salva. Vale até o backend reiniciar.')
    } catch (error) {
      setMessage(`Não foi possível salvar: ${(error as Error).message}`)
    }
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-1 font-semibold">Execução</h2>
        <p className="mb-3 text-sm text-slate-500">
          Replay usa respostas gravadas e não precisa de chave. Live chama as APIs de verdade.
        </p>
        <select
          className="rounded border border-slate-300 px-2 py-1"
          value={draft.mode}
          onChange={(e) => update({ mode: e.target.value as GraphConfig['mode'] })}
        >
          <option value="replay">Replay</option>
          <option value="live">Live</option>
        </select>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-3 font-semibold">Providers por node</h2>
        <div className="flex flex-col gap-3">
          {DECISION_NODES.map((node) => (
            <div key={node} className="flex items-center justify-between gap-4">
              <span>{NODE_LABELS[node]}</span>
              <div className="flex overflow-hidden rounded border border-slate-300">
                {MODES.map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() =>
                      update({
                        providers: { ...draft.providers, [node]: value },
                      })
                    }
                    className={`px-3 py-1 text-sm ${
                      draft.providers[node] === value
                        ? 'bg-indigo-600 text-white'
                        : 'bg-white text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-4 text-sm">
          <span>Primário em modo Ambos:</span>
          {(['jev', 'llm'] as const).map((provider) => (
            <label key={provider} className="flex items-center gap-1">
              <input
                type="radio"
                checked={draft.primary === provider}
                onChange={() => update({ primary: provider })}
              />
              {provider === 'jev' ? 'Jev' : 'LLM'}
            </label>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-3 font-semibold">Modelo de LLM</h2>
        <select
          className="w-full rounded border border-slate-300 px-2 py-1"
          value={draft.llm_model}
          onChange={(e) => update({ llm_model: e.target.value })}
        >
          {Object.entries(PROVIDER_GROUPS).map(([provider, label]) => (
            <optgroup key={provider} label={label}>
              {draft.catalog
                .filter((model) => model.provider === provider)
                .map((model) => (
                  <option key={model.model_id} value={`${provider}:${model.model_id}`}>
                    {model.label} · {formatPrice(pricing?.models[model.model_id])}
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
        <p className="mt-2 text-xs text-slate-500">
          Jev: {formatPrice(pricing?.models['jev-1.13.0'])}
          {pricing && ` · preços de ${pricing.reference_date}`}
        </p>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-3 font-semibold">Limiares</h2>
        <div className="flex flex-col gap-3">
          {THRESHOLDS.map(({ key, label }) => (
            <label key={key} className="flex items-center justify-between gap-4 text-sm">
              {label}
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={draft.thresholds[key]}
                onChange={(e) =>
                  update({
                    thresholds: {
                      ...draft.thresholds,
                      [key]: Number(e.target.value),
                    },
                  })
                }
                className="w-24 rounded border border-slate-300 px-2 py-1 text-right"
              />
            </label>
          ))}
        </div>
      </section>

      <div className="flex items-center gap-4">
        <button
          type="button"
          disabled={!dirty}
          onClick={save}
          className="rounded bg-indigo-600 px-4 py-2 font-medium text-white disabled:opacity-40"
        >
          Salvar
        </button>
        {message && <span className="text-sm text-slate-600">{message}</span>}
      </div>
    </div>
  )
}
