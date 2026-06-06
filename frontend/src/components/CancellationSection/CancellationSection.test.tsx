import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CancellationSection from './CancellationSection'
import {
  queryCarrierCancellations,
  queryRouteCancellations,
} from '../../db/queries'

vi.mock('../../db/queries', () => ({
  queryCarrierCancellations: vi.fn(),
  queryRouteCancellations: vi.fn(),
}))

vi.mock('highcharts-react-official', () => ({
  default: ({ options }: { options: Highcharts.Options }) => (
    <div
      data-testid={`hc-${(options.title?.text ?? 'untitled').toLowerCase().replace(/\s+/g, '-')}`}
    >
      {JSON.stringify(
        (options.series?.[0] as Highcharts.SeriesBarOptions | undefined)?.data ?? []
      )}
    </div>
  ),
}))

const mockCarrier = vi.mocked(queryCarrierCancellations)
const mockRoute = vi.mocked(queryRouteCancellations)

describe('CancellationSection', () => {
  beforeEach(() => {
    mockCarrier.mockReset()
    mockRoute.mockReset()
  })

  it('shows loading state while queries pending', () => {
    mockCarrier.mockReturnValue(new Promise(() => {}))
    mockRoute.mockReturnValue(new Promise(() => {}))
    render(<CancellationSection airportIcao="KJFK" />)
    expect(screen.getByText(/loading cancellation/i)).toBeInTheDocument()
    expect(screen.getByText(/loading/i)).toHaveAttribute('aria-busy', 'true')
  })

  it('shows empty state when no rows', async () => {
    mockCarrier.mockResolvedValue([])
    mockRoute.mockResolvedValue([])
    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() =>
      expect(screen.getByText(/no cancellation data/i)).toBeInTheDocument()
    )
  })

  it('shows error on rejected query', async () => {
    mockCarrier.mockRejectedValue(new Error('boom'))
    mockRoute.mockResolvedValue([])
    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/failed to load/i)
    )
  })

  it('renders carrier bar with top 10 sorted by rate desc', async () => {
    const carriers = Array.from({ length: 15 }, (_, i) => ({
      origin_icao: 'KJFK',
      carrier_icao: `C${i.toString().padStart(2, '0')}`,
      carrier_name: `Carrier ${i}`,
      total_scheduled: 1000,
      cancelled: 100 - i,
      cancellation_rate: (100 - i) / 1000,
      period_start: '2024-01-01',
      period_end: '2024-12-31',
    }))
    mockCarrier.mockResolvedValue(carriers)
    mockRoute.mockResolvedValue([])

    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() => expect(screen.getByTestId(/hc-carriers/)).toBeInTheDocument())

    const carrierEl = screen.getByTestId(/hc-carriers/)
    const data = JSON.parse(carrierEl.textContent ?? '[]') as Array<{ name: string }>
    expect(data).toHaveLength(10)
    expect(data[0].name).toBe('Carrier 0')
  })

  it('renders route bar with top 10 sorted by rate desc', async () => {
    mockCarrier.mockResolvedValue([])
    const routes = Array.from({ length: 12 }, (_, i) => ({
      origin_icao: 'KJFK',
      destination_icao: `KX${i.toString().padStart(2, '0')}`,
      total_scheduled: 500,
      cancelled: 50 - i,
      cancellation_rate: (50 - i) / 500,
      period_start: '2024-01-01',
      period_end: '2024-12-31',
    }))
    mockRoute.mockResolvedValue(routes)

    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() => expect(screen.getByTestId(/hc-routes/)).toBeInTheDocument())

    const routeEl = screen.getByTestId(/hc-routes/)
    const data = JSON.parse(routeEl.textContent ?? '[]') as Array<{ name: string }>
    expect(data).toHaveLength(10)
    expect(data[0].name).toBe('KJFK → KX00')
  })

  it('formats rate as percent in carrier bar data', async () => {
    mockCarrier.mockResolvedValue([
      {
        origin_icao: 'KJFK',
        carrier_icao: 'AAL',
        carrier_name: 'American Airlines',
        total_scheduled: 1000,
        cancelled: 12,
        cancellation_rate: 0.0123,
        period_start: '2024-01-01',
        period_end: '2024-12-31',
      },
    ])
    mockRoute.mockResolvedValue([])

    render(<CancellationSection airportIcao="KJFK" />)
    await waitFor(() => expect(screen.getByTestId(/hc-carriers/)).toBeInTheDocument())

    const data = JSON.parse(
      screen.getByTestId(/hc-carriers/).textContent ?? '[]'
    ) as Array<{ y: number }>
    // Highcharts wants percentage units → 1.23
    expect(data[0].y).toBeCloseTo(1.23, 2)
  })
})
