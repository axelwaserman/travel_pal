import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import SortBar from './SortBar'
import { SORT_VALUES } from '../../hooks/useFlightLookupParams'
import type { FlightLookupParams } from '../../hooks/useFlightLookupParams'

describe('SortBar', () => {
  const DEFAULT_SORT: FlightLookupParams['sort'] = 'on_time_desc'

  it('renders a select element', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('renders all 7 sort options', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(7)
  })

  it('displays correct label for on_time_desc', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'On-time ↓' })).toBeInTheDocument()
  })

  it('displays correct label for on_time_asc', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'On-time ↑' })).toBeInTheDocument()
  })

  it('displays correct label for delay_asc', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'Avg delay ↑' })).toBeInTheDocument()
  })

  it('displays correct label for delay_desc', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'Avg delay ↓' })).toBeInTheDocument()
  })

  it('displays correct label for volume_desc', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'Flights ↓' })).toBeInTheDocument()
  })

  it('displays correct label for volume_asc', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'Flights ↑' })).toBeInTheDocument()
  })

  it('displays correct label for volatility_asc', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'Volatility ↑' })).toBeInTheDocument()
  })

  it('reflects the current value as selected', () => {
    render(<SortBar value="delay_asc" onChange={vi.fn()} />)
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('delay_asc')
  })

  it('calls onChange with new sort value when selection changes', () => {
    const onChange = vi.fn()
    render(<SortBar value={DEFAULT_SORT} onChange={onChange} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'volume_desc' } })
    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange).toHaveBeenCalledWith('volume_desc')
  })

  it('calls onChange with volatility_asc when that option is selected', () => {
    const onChange = vi.fn()
    render(<SortBar value={DEFAULT_SORT} onChange={onChange} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'volatility_asc' } })
    expect(onChange).toHaveBeenCalledWith('volatility_asc')
  })

  it('does not call onChange when the select value is not in the SORT_VALUES allowlist', () => {
    // Regression: guard against arbitrary/injected values reaching onChange.
    const onChange = vi.fn()
    render(<SortBar value={DEFAULT_SORT} onChange={onChange} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '__evil__' } })
    expect(onChange).not.toHaveBeenCalled()
  })

  it('derives options from SORT_VALUES — renders exactly as many options as SORT_VALUES entries', () => {
    render(<SortBar value={DEFAULT_SORT} onChange={vi.fn()} />)
    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(SORT_VALUES.length)
  })
})
