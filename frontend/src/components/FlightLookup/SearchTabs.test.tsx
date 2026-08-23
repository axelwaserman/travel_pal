import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import SearchTabs from './SearchTabs'

describe('SearchTabs', () => {
  it('renders a tablist with two tabs', () => {
    render(<SearchTabs value="airports" onChange={vi.fn()} />)
    expect(screen.getByRole('tablist')).toBeInTheDocument()
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(2)
    expect(tabs[0]).toHaveTextContent('Airports')
    expect(tabs[1]).toHaveTextContent('Carriers')
  })

  it('marks the active tab with aria-selected="true"', () => {
    render(<SearchTabs value="airports" onChange={vi.fn()} />)
    const [airports, carriers] = screen.getAllByRole('tab')
    expect(airports).toHaveAttribute('aria-selected', 'true')
    expect(carriers).toHaveAttribute('aria-selected', 'false')
  })

  it('marks the correct tab when value is "carriers"', () => {
    render(<SearchTabs value="carriers" onChange={vi.fn()} />)
    const [airports, carriers] = screen.getAllByRole('tab')
    expect(airports).toHaveAttribute('aria-selected', 'false')
    expect(carriers).toHaveAttribute('aria-selected', 'true')
  })

  it('calls onChange with "carriers" when Carriers tab is clicked', () => {
    const onChange = vi.fn()
    render(<SearchTabs value="airports" onChange={onChange} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Carriers' }))
    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange).toHaveBeenCalledWith('carriers')
  })

  it('calls onChange with "airports" when Airports tab is clicked', () => {
    const onChange = vi.fn()
    render(<SearchTabs value="carriers" onChange={onChange} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Airports' }))
    expect(onChange).toHaveBeenCalledWith('airports')
  })

  it('does not call onChange when already-active tab is clicked', () => {
    const onChange = vi.fn()
    render(<SearchTabs value="airports" onChange={onChange} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Airports' }))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('moves focus to Carriers tab on ArrowRight when Airports is focused', () => {
    render(<SearchTabs value="airports" onChange={vi.fn()} />)
    const [airports, carriers] = screen.getAllByRole('tab')
    airports.focus()
    fireEvent.keyDown(airports, { key: 'ArrowRight' })
    expect(document.activeElement).toBe(carriers)
  })

  it('moves focus to Airports tab on ArrowLeft when Carriers is focused', () => {
    render(<SearchTabs value="carriers" onChange={vi.fn()} />)
    const [airports, carriers] = screen.getAllByRole('tab')
    carriers.focus()
    fireEvent.keyDown(carriers, { key: 'ArrowLeft' })
    expect(document.activeElement).toBe(airports)
  })

  it('wraps focus from Airports to Carriers on ArrowLeft', () => {
    render(<SearchTabs value="airports" onChange={vi.fn()} />)
    const [airports, carriers] = screen.getAllByRole('tab')
    airports.focus()
    fireEvent.keyDown(airports, { key: 'ArrowLeft' })
    expect(document.activeElement).toBe(carriers)
  })

  it('wraps focus from Carriers to Airports on ArrowRight', () => {
    render(<SearchTabs value="carriers" onChange={vi.fn()} />)
    const [airports, carriers] = screen.getAllByRole('tab')
    carriers.focus()
    fireEvent.keyDown(carriers, { key: 'ArrowRight' })
    expect(document.activeElement).toBe(airports)
  })

  it('Enter on a focused-but-not-selected Carriers tab fires onChange with "carriers"', () => {
    const onChange = vi.fn()
    render(<SearchTabs value="airports" onChange={onChange} />)
    const [, carriers] = screen.getAllByRole('tab')
    carriers.focus()
    fireEvent.keyDown(carriers, { key: 'Enter' })
    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange).toHaveBeenCalledWith('carriers')
  })

  it('Space on a focused-but-not-selected Carriers tab fires onChange with "carriers"', () => {
    const onChange = vi.fn()
    render(<SearchTabs value="airports" onChange={onChange} />)
    const [, carriers] = screen.getAllByRole('tab')
    carriers.focus()
    fireEvent.keyDown(carriers, { key: ' ' })
    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange).toHaveBeenCalledWith('carriers')
  })

  it('Enter on the already-active Airports tab still fires onChange', () => {
    const onChange = vi.fn()
    render(<SearchTabs value="airports" onChange={onChange} />)
    const [airports] = screen.getAllByRole('tab')
    airports.focus()
    fireEvent.keyDown(airports, { key: 'Enter' })
    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange).toHaveBeenCalledWith('airports')
  })
})
