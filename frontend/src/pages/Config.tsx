import { useEffect, useState } from 'react'

import { Badge, Button, Card, CardTitle, cx } from '../components/ui'
import { getTools, putConfig } from '../lib/api'
import { formatPrice } from '../lib/format'
import { DECISION_NODES, NODE_HINTS, NODE_LABELS } from '../lib/questions'
import type { GraphConfig, NodeMode, Pricing, Thresholds, Tool } from '../lib/types'

const MODES: { value: NodeMode; label: string }[] = [
  { value: 'llm', label: 'LLM' },
  { value: 'jev', label: 'Jev' },
  { value: 'both', label: 'Ambos' },
]

const THRESHOLDS: { key: keyof Thresholds; label: string; hint: string }[] = [
  {
    key: 'guardrail_block',
    label: 'Bloquear no guardrail com risco ≥',
    hint: 'Vale para manipulação, dado sensível e fora do escopo.',
  },
  {
    key: 'triage_min_confidence',
    label: 'Revisão humana se a confiança na consulta for <',
    hint: 'Confiança da triagem na tool escolhida.',
  },
  {
    key: 'verify_min_faithful',
    label: 'Revisão humana se "fiel aos dados" for <',
    hint: 'Probabilidade de a resposta só afirmar o que está nos dados.',
  },
  {
    key: 'verify_max_invented',
    label: 'Revisão humana se "inventa número" for ≥',
    hint: 'Probabilidade de a resposta citar número que não está nos dados.',
  },
]

const PROVIDER_GROUPS = { openai: 'OpenAI', anthropic: 'Anthropic' }

const sameConfig = (a: GraphConfig, b: GraphConfig) =>
  a.mode === b.mode &&
  a.primary === b.primary &&
  a.llm_model === b.llm_model &&
  DECISION_NODES.every((n) => a.providers[n] === b.providers[n]) &&
  (Object.keys(a.thresholds) as (keyof Thresholds)[]).every(
    (k) => a.thresholds[k] === b.thresholds[k],
  )

interface Props {
  config: GraphConfig
  pricing: Pricing | null
  onSaved: (config: GraphConfig) => void
}

export function Config({ config, pricing, onSaved }: Props) {
  const [draft, setDraft] = useState(config)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [tools, setTools] = useState<Tool[]>([])
  const dirty = !sameConfig(draft, config)

  useEffect(() => {
    getTools()
      .then(setTools)
      .catch(() => setTools([]))
  }, [])

  const update = (changes: Partial<GraphConfig>) => {
    setMessage(null)
    setDraft({ ...draft, ...changes })
  }

  async function save() {
    setSaving(true)
    try {
      const saved = await putConfig(draft)
      setDraft(saved)
      onSaved(saved)
      setMessage({ ok: true, text: 'Configuração salva. Vale até o backend reiniciar.' })
    } catch (error) {
      setMessage({ ok: false, text: `Não foi possível salvar: ${(error as Error).message}` })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <div className="flex flex-col gap-6">
        <Card>
          <CardTitle hint="Replay usa respostas gravadas e não precisa de chave nem de banco. Live chama as APIs e o Postgres de verdade.">
            Execução
          </CardTitle>
          <label className="flex flex-col gap-1 text-sm sm:max-w-xs">
            Modo
            <select
              className="rounded-lg border border-slate-300 px-3 py-2"
              value={draft.mode}
              onChange={(e) => update({ mode: e.target.value as GraphConfig['mode'] })}
            >
              <option value="replay">Replay</option>
              <option value="live">Live</option>
            </select>
          </label>
        </Card>

        <Card>
          <CardTitle hint="Quem decide em cada etapa. Em Ambos, os dois rodam em paralelo e só o primário segue no fluxo.">
            Providers por etapa
          </CardTitle>
          <div className="flex flex-col divide-y divide-slate-100">
            {DECISION_NODES.map((node) => (
              <div
                key={node}
                className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0"
              >
                <div>
                  <p className="text-sm font-medium" id={`mode-${node}`}>
                    {NODE_LABELS[node]}
                  </p>
                  <p className="text-xs text-slate-500">{NODE_HINTS[node]}</p>
                </div>
                <div
                  role="group"
                  aria-labelledby={`mode-${node}`}
                  className="flex rounded-lg bg-slate-100 p-1"
                >
                  {MODES.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={draft.providers[node] === value}
                      onClick={() => update({ providers: { ...draft.providers, [node]: value } })}
                      className={cx(
                        'rounded-md px-3 py-1 text-sm font-medium',
                        draft.providers[node] === value
                          ? 'bg-white text-slate-900 shadow-sm'
                          : 'text-slate-600 hover:text-slate-900',
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <fieldset className="mt-4 flex flex-wrap items-center gap-4 border-t border-slate-100 pt-4 text-sm">
            <legend className="sr-only">Primário em modo Ambos</legend>
            <span aria-hidden="true">Primário em modo Ambos:</span>
            {(['jev', 'llm'] as const).map((provider) => (
              <label key={provider} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="primary"
                  className="accent-brand-600"
                  checked={draft.primary === provider}
                  onChange={() => update({ primary: provider })}
                />
                <span
                  className={cx('size-2 rounded-full', provider === 'jev' ? 'bg-jev' : 'bg-llm')}
                  aria-hidden="true"
                />
                {provider === 'jev' ? 'Jev' : 'LLM'}
              </label>
            ))}
          </fieldset>
        </Card>

        <Card>
          <CardTitle hint="Usado nas decisões em modo LLM ou Ambos e sempre na resposta.">
            Modelo de LLM
          </CardTitle>
          <label className="flex flex-col gap-1 text-sm">
            <span className="sr-only">Modelo de LLM</span>
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
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
          </label>
          <p className="mt-2 text-xs text-slate-500">
            Jev: {formatPrice(pricing?.models['jev-1.13.0'])}
            {pricing && ` · preços de ${pricing.reference_date}`}
          </p>
        </Card>

        <Card>
          <CardTitle hint="Definem quando o agente bloqueia ou manda para revisão humana.">
            Limiares
          </CardTitle>
          <div className="flex flex-col gap-4">
            {THRESHOLDS.map(({ key, label, hint }) => (
              <label key={key} className="flex items-center justify-between gap-4 text-sm">
                <span>
                  {label}
                  <span className="block text-xs text-slate-500">{hint}</span>
                </span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={draft.thresholds[key]}
                  onChange={(e) =>
                    update({ thresholds: { ...draft.thresholds, [key]: Number(e.target.value) } })
                  }
                  className="w-24 shrink-0 rounded-lg border border-slate-300 px-3 py-1.5 text-right tabular-nums"
                />
              </label>
            ))}
          </div>
        </Card>

        <div className="flex flex-wrap items-center gap-4">
          <Button disabled={!dirty} loading={saving} onClick={save}>
            Salvar
          </Button>
          {dirty && !message && (
            <span className="text-sm text-slate-500">Há alterações não salvas.</span>
          )}
          {message && (
            <span
              role="status"
              className={cx('text-sm', message.ok ? 'text-emerald-700' : 'text-red-700')}
            >
              {message.text}
            </span>
          )}
        </div>
      </div>

      <Card className="self-start">
        <CardTitle hint="A triagem escolhe uma destas consultas. Cada uma lê uma view do Postgres; o modelo nunca escreve SQL.">
          Tools disponíveis
        </CardTitle>
        {tools.length === 0 ? (
          <p className="text-sm text-slate-500">Carregando…</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {tools.map((tool) => (
              <li key={tool.name}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{tool.title}</span>
                  <Badge className="font-mono">{tool.view}</Badge>
                </div>
                <p className="mt-0.5 text-xs text-slate-500">{tool.description}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
