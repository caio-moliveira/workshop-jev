import {
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
} from 'react'

/** Junta classes, ignorando as falsas. */
export const cx = (...classes: (string | false | null | undefined)[]) =>
  classes.filter(Boolean).join(' ')

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cx('rounded-card shadow-card border border-slate-200 bg-white p-5', className)}
      {...props}
    />
  )
}

export function CardTitle({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <header className="mb-4">
      <h2 className="text-base font-semibold text-slate-900">{children}</h2>
      {hint && <p className="mt-0.5 text-sm text-slate-500">{hint}</p>}
    </header>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'ghost'

const BUTTON: Record<ButtonVariant, string> = {
  primary: 'bg-brand-600 text-white shadow-sm hover:bg-brand-700 disabled:bg-slate-300',
  secondary:
    'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:text-slate-400',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 disabled:text-slate-400',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  loading?: boolean
}

export function Button({
  variant = 'primary',
  loading = false,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        'inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed motion-reduce:transition-none',
        BUTTON[variant],
        className,
      )}
      {...props}
    >
      {loading && <Spinner className="size-4" />}
      {children}
    </button>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cx('animate-spin motion-reduce:animate-none', className)}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

export type Tone = 'neutral' | 'brand' | 'ok' | 'warn' | 'danger' | 'jev' | 'llm'

const BADGE: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700',
  brand: 'bg-brand-50 text-brand-700',
  ok: 'bg-ok-soft text-emerald-800',
  warn: 'bg-warn-soft text-amber-800',
  danger: 'bg-danger-soft text-red-800',
  jev: 'bg-jev-soft text-jev',
  llm: 'bg-llm-soft text-orange-800',
}

export function Badge({
  tone = 'neutral',
  className,
  children,
}: {
  tone?: Tone
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        BADGE[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cx('animate-pulse rounded bg-slate-200 motion-reduce:animate-none', className)}
    />
  )
}

export function EmptyState({
  title,
  children,
  icon,
}: {
  title: string
  children?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
      {icon && <div className="text-slate-400">{icon}</div>}
      <p className="font-medium text-slate-700">{title}</p>
      {children && <div className="max-w-sm text-sm text-slate-500">{children}</div>}
    </div>
  )
}

export interface TabItem<T extends string> {
  id: T
  label: string
}

/** Abas acessíveis: setas e Home/End movem o foco e a seleção (padrão WAI-ARIA). */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
  idPrefix,
}: {
  items: TabItem<T>[]
  value: T
  onChange: (id: T) => void
  label: string
  idPrefix: string
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  function onKeyDown(event: KeyboardEvent, index: number) {
    const last = items.length - 1
    const next =
      event.key === 'ArrowRight'
        ? index === last
          ? 0
          : index + 1
        : event.key === 'ArrowLeft'
          ? index === 0
            ? last
            : index - 1
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : null
    if (next === null) return
    event.preventDefault()
    onChange(items[next].id)
    refs.current[next]?.focus()
  }

  return (
    <div role="tablist" aria-label={label} className="flex gap-1 rounded-lg bg-slate-100 p-1">
      {items.map((item, index) => {
        const selected = item.id === value
        return (
          <button
            key={item.id}
            ref={(el) => {
              refs.current[index] = el
            }}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${item.id}`}
            aria-selected={selected}
            aria-controls={`${idPrefix}-panel-${item.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.id)}
            onKeyDown={(e) => onKeyDown(e, index)}
            className={cx(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors motion-reduce:transition-none',
              selected
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900',
            )}
          >
            {item.label}
          </button>
        )
      })}
    </div>
  )
}

type Cell = string | number | boolean | null | undefined

const isNumeric = (value: Cell) => typeof value === 'number'

/** Coluna com algum valor fracionário mostra sempre duas casas: 333.990,10, não 333.990,1. */
function formatCell(value: Cell, fractional: boolean): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') {
    const digits = fractional ? 2 : 0
    return value.toLocaleString('pt-BR', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  }
  return String(value)
}

/** Tabela compacta e rolável, com cabeçalho fixo e números alinhados à direita. */
export function DataTable({
  columns,
  rows,
  caption,
  maxHeight = 'max-h-72',
}: {
  columns: string[]
  rows: Record<string, Cell>[]
  caption: string
  maxHeight?: string
}) {
  const captionId = useId()
  const numeric = new Set(columns.filter((c) => rows.some((r) => isNumeric(r[c]))))
  const fractional = new Set(
    columns.filter((c) => rows.some((r) => isNumeric(r[c]) && !Number.isInteger(r[c]))),
  )
  return (
    <div
      className={cx('overflow-auto rounded-lg border border-slate-200', maxHeight)}
      role="region"
      aria-labelledby={captionId}
      tabIndex={0}
    >
      <table className="w-full border-collapse text-left text-sm">
        <caption id={captionId} className="sr-only">
          {caption}
        </caption>
        <thead className="sticky top-0 bg-slate-50 text-xs text-slate-500">
          <tr>
            {columns.map((column) => (
              <th
                key={column}
                scope="col"
                className={cx(
                  'border-b border-slate-200 px-3 py-2 font-medium whitespace-nowrap',
                  numeric.has(column) && 'text-right',
                )}
              >
                {column.replaceAll('_', ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-slate-100 first:border-t-0 hover:bg-slate-50">
              {columns.map((column) => (
                <td
                  key={column}
                  className={cx(
                    'px-3 py-1.5 whitespace-nowrap',
                    numeric.has(column) && 'text-right tabular-nums',
                  )}
                >
                  {formatCell(row[column], fractional.has(column))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
