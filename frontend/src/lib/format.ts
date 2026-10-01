const number = new Intl.NumberFormat('pt-BR')

export const formatMs = (ms: number) =>
  ms >= 1000
    ? `${(ms / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} s`
    : `${Math.round(ms)} ms`

export const formatTokens = (tokens: number) => number.format(tokens)

export function formatUsd(value: number): string {
  if (value === 0) return 'US$ 0'
  const digits = value < 0.01 ? 6 : 4
  return `US$ ${value.toLocaleString('pt-BR', { maximumFractionDigits: digits })}`
}

export const formatPercent = (value: number) =>
  `${(value * 100).toLocaleString('pt-BR', { maximumFractionDigits: 0 })}%`

export function formatPrice(price: { input: number | null; output: number | null } | undefined) {
  if (!price || price.input === null || price.output === null) return 'preço não informado'
  const usd = (v: number) => v.toLocaleString('pt-BR', { maximumFractionDigits: 3 })
  return `US$ ${usd(price.input)} / ${usd(price.output)} por 1M`
}
