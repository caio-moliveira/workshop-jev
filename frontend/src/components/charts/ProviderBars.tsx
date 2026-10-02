import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

// Cores por provider, validadas com o script da skill de dataviz (CVD ΔE 24,7 sobre branco).
// A cor segue a entidade: o Jev é sempre azul e o LLM sempre laranja, em todo gráfico.
export const PROVIDER_COLORS = { jev: '#2a78d6', llm: '#eb6834' }
const PROVIDER_NAMES = { jev: 'Jev', llm: 'LLM' }

const INK = { axis: '#64748b', grid: '#e2e8f0' }

type Row = { [key: string]: string | number | null }

interface Props {
  title: string
  data: Row[]
  category: string
  format: (value: number) => string
  yLabel?: string
}

/** Barras agrupadas Jev × LLM por categoria, com um eixo só, legenda e tooltip. */
export function ProviderBars({ title, data, category, format, yLabel }: Props) {
  return (
    <figure className="rounded-card shadow-card border border-slate-200 bg-white p-4">
      <figcaption className="mb-3 text-sm font-semibold">{title}</figcaption>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} barGap={2} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid vertical={false} stroke={INK.grid} />
          <XAxis
            dataKey={category}
            interval={0}
            angle={-30}
            textAnchor="end"
            height={84}
            tick={{ fill: INK.axis, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: INK.grid }}
          />
          <YAxis
            tickFormatter={format}
            tick={{ fill: INK.axis, fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={88}
            label={
              yLabel
                ? {
                    value: yLabel,
                    angle: -90,
                    position: 'insideLeft',
                    fill: INK.axis,
                    fontSize: 12,
                  }
                : undefined
            }
          />
          <Tooltip
            formatter={(value, name) => [
              typeof value === 'number' ? format(value) : '—',
              PROVIDER_NAMES[name as 'jev' | 'llm'] ?? name,
            ]}
            cursor={{ fill: '#f1f5f9' }}
          />
          <Legend
            formatter={(name) => (
              <span className="text-sm text-slate-700">
                {PROVIDER_NAMES[name as 'jev' | 'llm']}
              </span>
            )}
          />
          {(['jev', 'llm'] as const).map((provider) => (
            <Bar
              key={provider}
              dataKey={provider}
              fill={PROVIDER_COLORS[provider]}
              radius={[4, 4, 0, 0]}
              maxBarSize={28}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
