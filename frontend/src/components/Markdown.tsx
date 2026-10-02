import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { cx } from './ui'

// Estilo de cada elemento com as classes do tema: o texto do LLM fica com a cara da tela.
// O react-markdown não interpreta HTML cru, então o que o modelo escrever não vira código.
const COMPONENTS: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  h1: ({ children }) => <p className="mb-2 font-semibold text-slate-900">{children}</p>,
  h2: ({ children }) => <p className="mb-2 font-semibold text-slate-900">{children}</p>,
  h3: ({ children }) => <p className="mb-2 font-semibold text-slate-900">{children}</p>,
  code: ({ children }) => (
    <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.9em]">{children}</code>
  ),
  table: ({ children }) => (
    <div className="mb-2 overflow-x-auto rounded-lg border border-slate-200 last:mb-0">
      <table className="w-full text-left text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-slate-50 text-xs text-slate-500">{children}</thead>,
  th: ({ children }) => <th className="px-3 py-1.5 font-medium">{children}</th>,
  td: ({ children }) => (
    <td className="border-t border-slate-100 px-3 py-1.5 tabular-nums">{children}</td>
  ),
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-brand-700 underline">
      {children}
    </a>
  ),
}

export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cx('break-words', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
