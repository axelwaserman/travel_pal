import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FlightLookup from './FlightLookup'
import * as queries from '../../db/queries'

vi.mock('../../db/queries', () => ({
  queryFlightLookup: vi.fn(),
  queryAirportSearch: vi.fn(),
  queryCarrierSearch: vi.fn(),
}))

// Mock useFlightLookupParams so tests can control URL state
vi.mock('../../hooks/useFlightLookupParams', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../hooks/useFlightLookupParams')>()
  return { ...actual }
})

// Mock ResultsBar (lazy) to avoid Highcharts in unit tests
vi.mock('./ResultsBar', () => ({
  ResultsBar: () => <div data-testid="results-bar" />,
}))

const mockAirportSearch = vi.mocked(queries.queryAirportSearch)
const mockCarrierSearch = vi.mocked(queries.queryCarrierSearch)

const AIRPORT_ROW = {
  origin_icao: 'KJFK',
  destination_icao: 'KLAX',
  total_flights: 1234,
  avg_delay_minutes: 5.2,
  delay_volatility: 12.1,
  on_time_ratio: 0.823,
  origin_name: 'JFK Airport',
  destination_name: 'LAX Airport',
}

const AIRPORT_ROW_B = {
  origin_icao: 'KJFK',
  destination_icao: 'KORD',
  total_flights: 500,
  avg_delay_minutes: 10.0,
  delay_volatility: 5.0,
  on_time_ratio: 0.650,
  origin_name: 'JFK Airport',
  destination_name: 'ORD Airport',
}

const CARRIER_ROW = {
  origin_icao: 'KJFK',
  carrier_icao: 'DAL',
  carrier_name: 'Delta Air Lines',
  total_scheduled: 2000,
  cancelled: 40,
  cancellation_rate: 0.02,
  period_start: '2024-01-01',
  period_end: '2024-12-31',
}

describe('FlightLookup', () => {
  beforeEach(() => {
    mockAirportSearch.mockReset()
    mockCarrierSearch.mockReset()
    // Reset URL search params between tests
    window.history.replaceState({}, '', '/')
  })

  // ── Existing behaviour (preserved) ───────────────────────────────────────

  it('renders heading and search controls', () => {
    render(<FlightLookup airportIcao="KJFK" />)
    expect(screen.getByRole('heading', { level: 2, name: 'Flight Lookup' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /flight route or airport/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument()
  })

  it('does not query when input is empty', () => {
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(mockAirportSearch).not.toHaveBeenCalled()
  })

  it('does not query when input is whitespace only', () => {
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(mockAirportSearch).not.toHaveBeenCalled()
  })

  it('queries with airport ICAO and trimmed search term on click (airports tab)', async () => {
    mockAirportSearch.mockResolvedValue([])
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '  KLAX  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(mockAirportSearch).toHaveBeenCalledWith('KJFK', 'KLAX'))
  })

  it('queries on Enter keypress', async () => {
    mockAirportSearch.mockResolvedValue([])
    render(<FlightLookup airportIcao="KJFK" />)
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'KLAX' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(mockAirportSearch).toHaveBeenCalledWith('KJFK', 'KLAX'))
  })

  it('disables button and shows "Searching…" during query', async () => {
    let resolveQuery: (v: never[]) => void
    mockAirportSearch.mockReturnValue(new Promise(r => { resolveQuery = r }))
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KLAX' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(screen.getByRole('button', { name: 'Searching…' })).toBeDisabled()
    act(() => { resolveQuery!([]) })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Search' })).not.toBeDisabled())
  })

  it('renders airport result cards on success', async () => {
    mockAirportSearch.mockResolvedValue([AIRPORT_ROW])
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KLAX' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(screen.getByText('KJFK → KLAX')).toBeInTheDocument())
    expect(screen.getByText('82.3%')).toBeInTheDocument()
    expect(screen.getByText('5.2 min')).toBeInTheDocument()
    expect(screen.getByText('1,234')).toBeInTheDocument()
  })

  it('renders em-dash for null fields without crashing', async () => {
    mockAirportSearch.mockResolvedValue([{
      ...AIRPORT_ROW,
      avg_delay_minutes: null,
      on_time_ratio: null,
    }])
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KLAX' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(screen.getByText('KJFK → KLAX')).toBeInTheDocument())
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })

  it('renders error message when query fails', async () => {
    mockAirportSearch.mockRejectedValue(new Error('boom'))
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KLAX' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/failed to load/i)
    )
  })

  // ── SearchTabs rendered ───────────────────────────────────────────────────

  it('renders both Airports and Carriers tabs', () => {
    render(<FlightLookup airportIcao="KJFK" />)
    expect(screen.getByRole('tab', { name: 'Airports' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Carriers' })).toBeInTheDocument()
  })

  // ── T7 TDD: 3 new failing tests ───────────────────────────────────────────

  it('T7: switching tab clears results, resets min to 1, and issues a new query for the new term', async () => {
    // Start with airports tab, results loaded
    mockAirportSearch.mockResolvedValue([AIRPORT_ROW])
    mockCarrierSearch.mockResolvedValue([])

    render(<FlightLookup airportIcao="KJFK" />)

    // Search on airports tab
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KLAX' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(screen.getByText('KJFK → KLAX')).toBeInTheDocument())

    // Switch to carriers tab — should clear results and trigger new query
    const carriersTab = screen.getByRole('tab', { name: 'Carriers' })
    fireEvent.click(carriersTab)

    // Results from airports tab must be gone
    await waitFor(() => expect(screen.queryByText('KJFK → KLAX')).not.toBeInTheDocument())

    // Min slider must be back to 1 (its default label)
    expect(screen.getByText('≥ 1 flights')).toBeInTheDocument()

    // queryCarrierSearch must have been called for the current term
    await waitFor(() => expect(mockCarrierSearch).toHaveBeenCalledWith('KJFK', 'KLAX'))
  })

  it('T7: changing sort re-orders displayed results without issuing a new query', async () => {
    // Two results: high on_time first, low on_time second
    mockAirportSearch.mockResolvedValue([AIRPORT_ROW, AIRPORT_ROW_B])

    render(<FlightLookup airportIcao="KJFK" />)

    // Load results
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KJFK' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(screen.getByText('KJFK → KLAX')).toBeInTheDocument())
    expect(screen.getByText('KJFK → KORD')).toBeInTheDocument()

    // Record how many times query was called so far
    const callsBefore = mockAirportSearch.mock.calls.length

    // Change sort to on_time_asc — lower on_time route (KORD) should appear before KLAX
    const sortSelect = screen.getByRole('combobox', { name: /sort results/i })
    fireEvent.change(sortSelect, { target: { value: 'on_time_asc' } })

    // No additional query must be issued
    expect(mockAirportSearch.mock.calls.length).toBe(callsBefore)

    // Order: KORD (0.65) before KLAX (0.82)
    const cards = screen.getAllByRole('article')
    expect(cards[0]).toHaveTextContent('KJFK → KORD')
    expect(cards[1]).toHaveTextContent('KJFK → KLAX')
  })

  it('T7: changing min slider filters results client-side without re-querying', async () => {
    // AIRPORT_ROW has 1234 flights, AIRPORT_ROW_B has 500
    mockAirportSearch.mockResolvedValue([AIRPORT_ROW, AIRPORT_ROW_B])

    render(<FlightLookup airportIcao="KJFK" />)

    // Load results
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KJFK' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => {
      expect(screen.getByText('KJFK → KLAX')).toBeInTheDocument()
      expect(screen.getByText('KJFK → KORD')).toBeInTheDocument()
    })

    const callsBefore = mockAirportSearch.mock.calls.length

    // Raise min slider above 500 but below 1234 — KORD should disappear
    const slider = screen.getByRole('slider', { name: /minimum flights/i })
    // Immediately fire change (bypass debounce by setting value directly)
    fireEvent.change(slider, { target: { value: '600' } })

    // Debounce fires after 300ms — fast-forward by waiting for KORD to vanish
    await waitFor(() => expect(screen.queryByText('KJFK → KORD')).not.toBeInTheDocument())

    // KLAX (1234 flights) still visible
    expect(screen.getByText('KJFK → KLAX')).toBeInTheDocument()

    // No re-query
    expect(mockAirportSearch.mock.calls.length).toBe(callsBefore)
  })

  // ── Carrier tab card rendering ────────────────────────────────────────────

  it('renders carrier cards with carrier_name, carrier_icao, and cancellation_rate', async () => {
    mockCarrierSearch.mockResolvedValue([CARRIER_ROW])

    render(<FlightLookup airportIcao="KJFK" />)

    // Switch to Carriers tab
    fireEvent.click(screen.getByRole('tab', { name: 'Carriers' }))

    // Type term and search
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'DAL' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => expect(screen.getByText('DAL')).toBeInTheDocument())
    expect(screen.getByText('Delta Air Lines')).toBeInTheDocument()
    // cancellation_rate 0.02 = 2.0%
    expect(screen.getByText('2.0%')).toBeInTheDocument()
  })

  // ── Empty states ──────────────────────────────────────────────────────────

  it('shows begin-prompt when no query has been typed', () => {
    render(<FlightLookup airportIcao="KJFK" />)
    expect(
      screen.getByText(/type an airport/i)
    ).toBeInTheDocument()
  })

  it('shows "no routes found" when query returns 0 results', async () => {
    mockAirportSearch.mockResolvedValue([])
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'ZZZZ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() =>
      expect(screen.getByText(/no routes found for/i)).toBeInTheDocument()
    )
  })

  it('shows threshold empty-state when min filter removes all results', async () => {
    mockAirportSearch.mockResolvedValue([AIRPORT_ROW_B]) // 500 flights
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KJFK' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(screen.getByText('KJFK → KORD')).toBeInTheDocument())

    // Set min above 500
    const slider = screen.getByRole('slider', { name: /minimum flights/i })
    fireEvent.change(slider, { target: { value: '600' } })

    await waitFor(() =>
      expect(screen.getByText(/0 of 1 results meet/i)).toBeInTheDocument()
    )
  })
})
