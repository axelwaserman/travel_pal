import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as queries from '../../db/queries'

// RoutePanel imports sub-charts lazily; mock them to avoid Highcharts in unit tests
vi.mock('./RoutePanelDailySparkline', () => ({
  RoutePanelDailySparkline: ({ data }: { data: unknown }) =>
    Array.isArray(data)
      ? <div data-testid="daily-sparkline" />
      : <div data-testid="daily-sparkline-error">{(data as { error: string }).error}</div>,
}))
vi.mock('./RoutePanelCarrierBreakdown', () => ({
  RoutePanelCarrierBreakdown: ({ data }: { data: unknown }) =>
    Array.isArray(data)
      ? <div data-testid="carrier-breakdown" />
      : <div data-testid="carrier-breakdown-error">{(data as { error: string }).error}</div>,
}))
vi.mock('./RoutePanelReasonMix', () => ({
  RoutePanelReasonMix: ({ data }: { data: unknown }) =>
    Array.isArray(data)
      ? <div data-testid="reason-mix" />
      : <div data-testid="reason-mix-error">{(data as { error: string }).error}</div>,
}))

vi.mock('../../db/queries', () => ({
  queryRouteDaily: vi.fn(),
  queryRouteCarriers: vi.fn(),
  queryRouteReasons: vi.fn(),
}))

const mockQueryRouteDaily = vi.mocked(queries.queryRouteDaily)
const mockQueryRouteCarriers = vi.mocked(queries.queryRouteCarriers)
const mockQueryRouteReasons = vi.mocked(queries.queryRouteReasons)

// Import RoutePanel after mocks are set up
const { RoutePanel } = await import('./RoutePanel')

describe('RoutePanel', () => {
  const onClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockQueryRouteDaily.mockResolvedValue([])
    mockQueryRouteCarriers.mockResolvedValue([])
    mockQueryRouteReasons.mockResolvedValue([])
  })

  it('mounts and runs 3 queries via Promise.allSettled when route is provided', async () => {
    await act(async () => {
      render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
    })
    await waitFor(() => {
      expect(mockQueryRouteDaily).toHaveBeenCalledWith('KJFK', 'KLAX')
      expect(mockQueryRouteCarriers).toHaveBeenCalledWith('KJFK', 'KLAX')
      expect(mockQueryRouteReasons).toHaveBeenCalledWith('KJFK', 'KLAX')
    })
  })

  it('renders the route heading and dialog role', async () => {
    await act(async () => {
      render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
    })
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('KJFK → KLAX')).toBeInTheDocument()
  })

  it('renders all 3 sub-charts once data loads', async () => {
    await act(async () => {
      render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
    })
    await waitFor(() => {
      expect(screen.getByTestId('daily-sparkline')).toBeInTheDocument()
      expect(screen.getByTestId('carrier-breakdown')).toBeInTheDocument()
      expect(screen.getByTestId('reason-mix')).toBeInTheDocument()
    })
  })

  it('Escape key calls onClose', async () => {
    await act(async () => {
      render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
    })
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('clicking outside the panel calls onClose', async () => {
    await act(async () => {
      render(
        <div>
          <RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />
          <button data-testid="outside">outside</button>
        </div>
      )
    })
    fireEvent.mouseDown(screen.getByTestId('outside'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('clicking the X button calls onClose', async () => {
    await act(async () => {
      render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
    })
    fireEvent.click(screen.getByRole('button', { name: /close panel/i }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('focus moves to close button on mount', async () => {
    await act(async () => {
      render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
    })
    const closeBtn = screen.getByRole('button', { name: /close panel/i })
    expect(document.activeElement).toBe(closeBtn)
  })

  it('restores focus to triggering element on close', async () => {
    const trigger = document.createElement('button')
    trigger.setAttribute('data-testid', 'trigger')
    document.body.appendChild(trigger)
    trigger.focus()

    let unmount!: () => void
    await act(async () => {
      const result = render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
      unmount = result.unmount
    })

    act(() => { unmount() })
    // Focus should have been restored to the element that was active before mount
    expect(document.activeElement).toBe(trigger)
    document.body.removeChild(trigger)
  })

  it('one failing query shows an error banner in that sub-chart but others still render', async () => {
    mockQueryRouteDaily.mockRejectedValue(new Error('daily failed'))
    mockQueryRouteCarriers.mockResolvedValue([])
    mockQueryRouteReasons.mockResolvedValue([])

    await act(async () => {
      render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
    })
    await waitFor(() => {
      expect(screen.getByTestId('daily-sparkline-error')).toBeInTheDocument()
      expect(screen.getByTestId('carrier-breakdown')).toBeInTheDocument()
      expect(screen.getByTestId('reason-mix')).toBeInTheDocument()
    })
  })

  it('Tab from the close button wraps focus back to the close button (only focusable element)', async () => {
    await act(async () => {
      render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
    })
    const closeBtn = screen.getByRole('button', { name: /close panel/i })
    closeBtn.focus()
    expect(document.activeElement).toBe(closeBtn)

    // Tab when only one focusable element: focus must stay on the close button
    fireEvent.keyDown(closeBtn, { key: 'Tab', shiftKey: false })
    expect(document.activeElement).toBe(closeBtn)

    // Shift-Tab must also stay on the close button
    fireEvent.keyDown(closeBtn, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(closeBtn)
  })

  it('has aria-modal=true and aria-labelledby pointing at the route heading', async () => {
    await act(async () => {
      render(<RoutePanel origin="KJFK" destination="KLAX" onClose={onClose} />)
    })
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    const labelId = dialog.getAttribute('aria-labelledby')
    expect(labelId).toBeTruthy()
    const heading = document.getElementById(labelId!)
    expect(heading).toBeInTheDocument()
    expect(heading!.textContent).toContain('KJFK')
  })
})
