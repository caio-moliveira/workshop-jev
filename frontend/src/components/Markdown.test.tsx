// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { Markdown } from './Markdown'

afterEach(cleanup)

describe('Markdown', () => {
  it('negrito vira <strong>, sem os asteriscos na tela', () => {
    const { container } = render(<Markdown>{'Quem mais vendeu foi **Diego Martins**.'}</Markdown>)

    expect(screen.getByText('Diego Martins').tagName).toBe('STRONG')
    expect(container.textContent).not.toContain('**')
  })

  it('listas e tabelas do GFM', () => {
    render(
      <Markdown>
        {'- Sudeste\n- Sul\n\n| Região | Receita |\n|---|---|\n| Norte | R$ 10 |'}
      </Markdown>,
    )

    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByRole('table')).toBeTruthy()
    expect(screen.getByText('R$ 10').tagName).toBe('TD')
  })

  it('HTML no texto do modelo não vira elemento', () => {
    const { container } = render(<Markdown>{'Oi <script>alert(1)</script><b>x</b>'}</Markdown>)

    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
  })
})
