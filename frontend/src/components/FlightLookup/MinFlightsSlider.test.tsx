import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import MinFlightsSlider from './MinFlightsSlider'

describe('MinFlightsSlider', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders a range input', () => {
    render(<MinFlightsSlider value={1} onChange={vi.fn()} />)
    expect(screen.getByRole('slider')).toBeInTheDocument()
  })

  it('has min=1 and max=1000', () => {
    render(<MinFlightsSlider value={1} onChange={vi.fn()} />)
    const slider = screen.getByRole('slider') as HTMLInputElement
    expect(slider.min).toBe('1')
    expect(slider.max).toBe('1000')
  })

  it('reflects the current value', () => {
    render(<MinFlightsSlider value={500} onChange={vi.fn()} />)
    const slider = screen.getByRole('slider') as HTMLInputElement
    expect(slider.value).toBe('500')
  })

  it('has correct aria attributes', () => {
    render(<MinFlightsSlider value={100} onChange={vi.fn()} />)
    const slider = screen.getByRole('slider')
    expect(slider).toHaveAttribute('aria-valuemin', '1')
    expect(slider).toHaveAttribute('aria-valuemax', '1000')
    expect(slider).toHaveAttribute('aria-valuenow', '100')
    expect(slider).toHaveAttribute('aria-label', 'Minimum flights threshold')
  })

  it('displays the current value as "≥ N flights"', () => {
    render(<MinFlightsSlider value={100} onChange={vi.fn()} />)
    expect(screen.getByText('≥ 100 flights')).toBeInTheDocument()
  })

  it('updates the displayed value immediately when slider moves (before debounce fires)', () => {
    render(<MinFlightsSlider value={1} onChange={vi.fn()} />)
    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '250' } })
    expect(screen.getByText('≥ 250 flights')).toBeInTheDocument()
  })

  it('debounces onChange: does not fire immediately on change', () => {
    const onChange = vi.fn()
    render(<MinFlightsSlider value={1} onChange={onChange} />)
    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '250' } })
    expect(onChange).not.toHaveBeenCalled()
  })

  it('fires onChange after default 300ms debounce', () => {
    const onChange = vi.fn()
    render(<MinFlightsSlider value={1} onChange={onChange} />)
    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '250' } })
    act(() => { vi.advanceTimersByTime(300) })
    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange).toHaveBeenCalledWith(250)
  })

  it('coalesces rapid changes — only fires once with the last value', () => {
    const onChange = vi.fn()
    render(<MinFlightsSlider value={1} onChange={onChange} />)
    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '100' } })
    fireEvent.change(slider, { target: { value: '200' } })
    fireEvent.change(slider, { target: { value: '300' } })
    act(() => { vi.advanceTimersByTime(300) })
    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange).toHaveBeenCalledWith(300)
  })

  it('respects a custom debounceMs prop', () => {
    const onChange = vi.fn()
    render(<MinFlightsSlider value={1} onChange={onChange} debounceMs={500} />)
    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '100' } })
    act(() => { vi.advanceTimersByTime(300) })
    expect(onChange).not.toHaveBeenCalled()
    act(() => { vi.advanceTimersByTime(200) })
    expect(onChange).toHaveBeenCalledWith(100)
  })

  it('calls onChange with an integer, not a string', () => {
    const onChange = vi.fn()
    render(<MinFlightsSlider value={1} onChange={onChange} />)
    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '42' } })
    act(() => { vi.advanceTimersByTime(300) })
    expect(onChange).toHaveBeenCalledWith(42)
    expect(typeof onChange.mock.calls[0][0]).toBe('number')
  })

  it('cancels pending debounce when parent resets value externally', () => {
    // Regression: stale timer must not fire after parent resets value prop.
    const onChange = vi.fn()
    const { rerender } = render(<MinFlightsSlider value={500} onChange={onChange} />)
    const slider = screen.getByRole('slider')

    // User drags to 700 — starts a 300ms debounce
    fireEvent.change(slider, { target: { value: '700' } })

    // Parent immediately resets to 1 (e.g. URL reset) before debounce fires
    rerender(<MinFlightsSlider value={1} onChange={onChange} />)

    // Advance past the original debounce window
    act(() => { vi.advanceTimersByTime(300) })

    // The stale timer should have been cancelled; onChange must not be called
    expect(onChange).not.toHaveBeenCalled()
  })
})
