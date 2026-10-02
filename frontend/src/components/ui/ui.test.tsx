// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { TOOL } from '../../test/runs'
import { DataTable, Tabs } from '.'

afterEach(cleanup)

describe('DataTable', () => {
  it('mostra as colunas e as linhas do resultado da consulta', () => {
    render(<DataTable columns={TOOL.columns} rows={TOOL.rows} caption="Dados" />)

    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual([
      'mes',
      'receita',
    ])
    expect(screen.getAllByRole('row')).toHaveLength(3)
    expect(screen.getByText('2026-09')).toBeTruthy()
    expect(screen.getByText('578.064,86')).toBeTruthy()
    expect(screen.getByText('470.878,15')).toBeTruthy()
  })

  it('números alinhados à direita e valor vazio como travessão', () => {
    render(
      <DataTable
        columns={['nome', 'valor']}
        rows={[
          { nome: 'Sul', valor: null },
          { nome: 'Norte', valor: 3 },
        ]}
        caption="Dados"
      />,
    )

    expect(screen.getByText('3').className).toContain('text-right')
    expect(screen.getByText('—')).toBeTruthy()
  })
})

function Harness() {
  const [tab, setTab] = useState<'a' | 'b' | 'c'>('a')
  return (
    <Tabs
      items={[
        { id: 'a', label: 'A' },
        { id: 'b', label: 'B' },
        { id: 'c', label: 'C' },
      ]}
      value={tab}
      onChange={setTab}
      label="Seções"
      idPrefix="t"
    />
  )
}

describe('Tabs', () => {
  it('marca a aba selecionada e navega pelas setas', () => {
    render(<Harness />)
    const [a, b, c] = screen.getAllByRole('tab')
    expect(a.getAttribute('aria-selected')).toBe('true')
    expect(b.tabIndex).toBe(-1)

    fireEvent.keyDown(a, { key: 'ArrowRight' })
    expect(b.getAttribute('aria-selected')).toBe('true')

    fireEvent.keyDown(b, { key: 'End' })
    expect(c.getAttribute('aria-selected')).toBe('true')

    fireEvent.keyDown(c, { key: 'ArrowRight' })
    expect(a.getAttribute('aria-selected')).toBe('true')
  })
})
