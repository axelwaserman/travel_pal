import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FlightLookup from './FlightLookup'
import { queryFlightLookup } from '../../db/queries'

vi.mock('../../db/queries', () => ({
  queryFlightLookup: vi.fn(),
}))

const mockQuery = vi.mocked(queryFlightLookup)

describe('FlightLookup', () => {
  beforeEach(() => {
    mockQuery.mockReset()
  })

  it('renders heading and search controls', () => {
    render(<FlightLookup airportIcao="KJFK" />)
    expect(screen.getByRole('heading', { level: 2, name: 'Flight Lookup' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /flight route or airport/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument()
  })

  it('does not query when input is empty', () => {
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(mockQuery).not.toHaveBeenCalled()
  })

  it('does not query when input is whitespace only', () => {
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(mockQuery).not.toHaveBeenCalled()
  })

  it('queries with airport ICAO and trimmed search term on click', async () => {
    mockQuery.mockResolvedValue([])
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '  KLAX  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(mockQuery).toHaveBeenCalledWith('KJFK', 'KLAX'))
  })

  it('queries on Enter keypress', async () => {
    mockQuery.mockResolvedValue([])
    render(<FlightLookup airportIcao="KJFK" />)
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'KLAX' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(mockQuery).toHaveBeenCalledWith('KJFK', 'KLAX'))
  })

  it('disables button and shows "Searching…" during query', async () => {
    let resolveQuery: (v: never[]) => void
    mockQuery.mockReturnValue(new Promise(r => { resolveQuery = r }))
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KLAX' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(screen.getByRole('button', { name: 'Searching…' })).toBeDisabled()
    resolveQuery!([])
    await waitFor(() => expect(screen.getByRole('button', { name: 'Search' })).not.toBeDisabled())
  })

  it('renders result cards on success', async () => {
    mockQuery.mockResolvedValue([
      {
        origin_icao: 'KJFK',
        destination_icao: 'KLAX',
        total_flights: 1234,
        avg_delay_minutes: 5.2,
        delay_volatility: 12.1,
        on_time_ratio: 0.823,
      },
    ])
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KLAX' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(screen.getByText('KJFK → KLAX')).toBeInTheDocument())
    expect(screen.getByText('82.3%')).toBeInTheDocument()
    expect(screen.getByText('5.2 min')).toBeInTheDocument()
    expect(screen.getByText('1,234')).toBeInTheDocument()
  })

  it('renders em-dash for null fields without crashing', async () => {
    mockQuery.mockResolvedValue([
      {
        origin_icao: 'KJFK',
        destination_icao: 'KLAX',
        total_flights: 1,
        avg_delay_minutes: null,
        delay_volatility: null,
        on_time_ratio: null,
      },
    ])
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KLAX' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(screen.getByText('KJFK → KLAX')).toBeInTheDocument())
    // on_time_ratio dd shows '—'; avg_delay dd shows '—'
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })

  it('renders error message when query fails', async () => {
    mockQuery.mockRejectedValue(new Error('boom'))
    render(<FlightLookup airportIcao="KJFK" />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'KLAX' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/failed to load/i)
    )
  })
})
