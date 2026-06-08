import { describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { parsePartial } from './queries'

const Schema = z.object({ id: z.number(), name: z.string() })

describe('parsePartial', () => {
  it('returns parsed rows when all valid', () => {
    const rows = [
      { id: 1, name: 'a' },
      { id: 2, name: 'b' },
    ]
    expect(parsePartial(Schema, rows, 'test')).toEqual(rows)
  })

  it('drops invalid rows and logs a warning', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const rows = [
      { id: 1, name: 'a' },
      { id: 'bad', name: 'b' }, // invalid
      { id: 3, name: 'c' },
    ]
    const result = parsePartial(Schema, rows, 'test')
    expect(result).toEqual([
      { id: 1, name: 'a' },
      { id: 3, name: 'c' },
    ])
    expect(warn).toHaveBeenCalledOnce()
    warn.mockRestore()
  })

  it('returns empty array when all rows invalid', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const rows = [{ id: 'x' }, { id: 'y' }]
    expect(parsePartial(Schema, rows, 'test')).toEqual([])
    expect(warn).toHaveBeenCalledOnce()
    warn.mockRestore()
  })
})
