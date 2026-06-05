import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TimelinessDashboard from './TimelinessDashboard'
import { queryDailyTimeliness } from '../../db/queries'

vi.mock('../../db/queries', () => ({
  queryDailyTimeliness: vi.fn(),
}))

const mockQuery = vi.mocked(queryDailyTimeliness)

describe('TimelinessDashboard', () => {
  beforeEach(() => {
    mockQuery.mockReset()
  })

  it('shows loading state while query is pending', () => {
    mockQuery.mockReturnValue(new Promise(() => {})) // never resolves
    render(<TimelinessDashboard airportIcao="KJFK" />)
    expect(screen.getByText(/loading timeliness data/i)).toBeInTheDocument()
    expect(screen.getByText(/loading/i)).toHaveAttribute('aria-busy', 'true')
  })

  it('shows empty-state message when no data', async () => {
    mockQuery.mockResolvedValue([])
    render(<TimelinessDashboard airportIcao="KJFK" />)
    await waitFor(() => expect(screen.getByText(/no data available/i)).toBeInTheDocument())
  })

  it('shows error message on query failure', async () => {
    mockQuery.mockRejectedValue(new Error('boom'))
    render(<TimelinessDashboard airportIcao="KJFK" />)
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/failed to load/i)
    )
  })

  it('renders heading, metric cards, and table on success', async () => {
    mockQuery.mockResolvedValue([
      {
        flight_date: '2024-01-01',
        origin_icao: 'KJFK',
        total_flights: 100,
        avg_delay_minutes: 4.0,
        delay_volatility: 10.0,
        on_time_ratio: 0.8,
      },
      {
        flight_date: '2024-01-02',
        origin_icao: 'KJFK',
        total_flights: 200,
        avg_delay_minutes: 6.0,
        delay_volatility: 14.0,
        on_time_ratio: 0.9,
      },
    ])
    render(<TimelinessDashboard airportIcao="KJFK" />)

    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 2, name: /historic timeliness — kjfk/i })).toBeInTheDocument()
    )

    // Average values: on_time_ratio = (0.8 + 0.9)/2 = 0.85 -> 85.0%
    expect(screen.getByText('85.0%')).toBeInTheDocument()
    // avg_delay = (4 + 6)/2 = 5.0
    expect(screen.getByText('5.0 min')).toBeInTheDocument()
    // volatility = (10 + 14)/2 = 12.0
    expect(screen.getByText('12.0 min')).toBeInTheDocument()

    // Table rows
    expect(screen.getByText('2024-01-01')).toBeInTheDocument()
    expect(screen.getByText('2024-01-02')).toBeInTheDocument()
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('200')).toBeInTheDocument()
  })

  it('renders em-dash for null aggregate values without crashing', async () => {
    mockQuery.mockResolvedValue([
      {
        flight_date: '2024-01-01',
        origin_icao: 'KJFK',
        total_flights: 1,
        avg_delay_minutes: null,
        delay_volatility: null,
        on_time_ratio: null,
      },
    ])
    render(<TimelinessDashboard airportIcao="KJFK" />)
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument()
    )
    // Metric cards: on_time '—', avg_delay '— min', volatility '— min'.
    // Table row: '—' (pct), '—' (avg_delay), '—' (volatility).
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(4)
    expect(screen.getAllByText('— min').length).toBe(2)
  })

  it('mean returns null when every row has null for the column', async () => {
    mockQuery.mockResolvedValue([
      {
        flight_date: '2024-01-01',
        origin_icao: 'KJFK',
        total_flights: 10,
        avg_delay_minutes: null,
        delay_volatility: 8.0,
        on_time_ratio: 0.5,
      },
      {
        flight_date: '2024-01-02',
        origin_icao: 'KJFK',
        total_flights: 20,
        avg_delay_minutes: null,
        delay_volatility: 12.0,
        on_time_ratio: 0.7,
      },
    ])
    render(<TimelinessDashboard airportIcao="KJFK" />)
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument()
    )
    // avg_delay metric card → '— min'; on_time_ratio = 0.6 → '60.0%'; volatility = 10.0 → '10.0 min'
    expect(screen.getByText('60.0%')).toBeInTheDocument()
    expect(screen.getByText('10.0 min')).toBeInTheDocument()
    expect(screen.getByText('— min')).toBeInTheDocument()
  })
})
