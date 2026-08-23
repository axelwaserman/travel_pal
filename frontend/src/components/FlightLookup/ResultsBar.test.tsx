import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { Suspense } from 'react'
import type { RouteTimeliness } from '../../db/schemas'

vi.mock('highcharts-react-official', () => ({
  default: ({
    options,
    containerProps,
  }: {
    options: Highcharts.Options
    containerProps?: Record<string, string>
  }) => (
    <div
      data-testid={`hc-${(options.title?.text ?? 'untitled').toLowerCase().replace(/\s+/g, '-')}`}
      aria-label={containerProps?.['aria-label']}
      role={containerProps?.['role']}
    >
      {JSON.stringify(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (options.series?.[0] as any)?.data ?? []
      )}
    </div>
  ),
}))

// ResultsBar is a named export lazy-loaded via dynamic import.
// Import it directly for unit tests — Suspense wrapper is required.
import { ResultsBar } from './ResultsBar'

const makeRoute = (
  origin: string,
  destination: string,
  on_time_ratio: number | null,
  total_flights = 100
): RouteTimeliness => ({
  origin_icao: origin,
  destination_icao: destination,
  total_flights,
  avg_delay_minutes: 5,
  delay_volatility: 2,
  on_time_ratio,
})

function renderWithSuspense(ui: React.ReactElement) {
  return render(<Suspense fallback={<div>Loading…</div>}>{ui}</Suspense>)
}

describe('ResultsBar', () => {
  it('renders a Highcharts column chart titled with the airport ICAO', () => {
    const results = [makeRoute('KJFK', 'KLAX', 0.85)]
    renderWithSuspense(<ResultsBar results={results} airportIcao="KJFK" />)
    expect(screen.getByTestId(/hc-results-/)).toBeInTheDocument()
  })

  it('filters out rows with null on_time_ratio', () => {
    const results = [
      makeRoute('KJFK', 'KLAX', 0.85),
      makeRoute('KJFK', 'KORD', null),
      makeRoute('KJFK', 'KSFO', 0.72),
    ]
    renderWithSuspense(<ResultsBar results={results} airportIcao="KJFK" />)
    const el = screen.getByTestId(/hc-results-/)
    const data = JSON.parse(el.textContent ?? '[]') as Array<{ name: string }>
    expect(data).toHaveLength(2)
    expect(data.map(d => d.name)).not.toContain('KJFK → KORD')
  })

  it('caps to top 30 results', () => {
    const results = Array.from({ length: 40 }, (_, i) =>
      makeRoute('KJFK', `KX${i.toString().padStart(2, '0')}`, (40 - i) / 100)
    )
    renderWithSuspense(<ResultsBar results={results} airportIcao="KJFK" />)
    const el = screen.getByTestId(/hc-results-/)
    const data = JSON.parse(el.textContent ?? '[]') as unknown[]
    expect(data).toHaveLength(30)
  })

  it('formats x-axis label as "origin → destination"', () => {
    const results = [makeRoute('KJFK', 'KLAX', 0.9)]
    renderWithSuspense(<ResultsBar results={results} airportIcao="KJFK" />)
    const el = screen.getByTestId(/hc-results-/)
    const data = JSON.parse(el.textContent ?? '[]') as Array<{ name: string }>
    expect(data[0].name).toBe('KJFK → KLAX')
  })

  it('converts on_time_ratio to percentage (×100) on y-axis', () => {
    const results = [makeRoute('KJFK', 'KLAX', 0.823)]
    renderWithSuspense(<ResultsBar results={results} airportIcao="KJFK" />)
    const el = screen.getByTestId(/hc-results-/)
    const data = JSON.parse(el.textContent ?? '[]') as Array<{ y: number }>
    expect(data[0].y).toBeCloseTo(82.3, 1)
  })

  it('renders nothing (no chart element) when results is empty', () => {
    renderWithSuspense(<ResultsBar results={[]} airportIcao="KJFK" />)
    expect(screen.queryByTestId(/hc-results-/)).not.toBeInTheDocument()
  })

  it('chart container has aria-label with airport ICAO and role=img', () => {
    const results = [makeRoute('EGLL', 'LFPG', 0.78)]
    renderWithSuspense(<ResultsBar results={results} airportIcao="EGLL" />)
    const el = screen.getByTestId(/hc-results-/)
    expect(el).toHaveAttribute('aria-label', 'On-time ratio by route — EGLL')
    expect(el).toHaveAttribute('role', 'img')
  })

  it('sorts by on_time_ratio desc before slicing to top 30', () => {
    // 32 rows in shuffled order — worst routes first, best last
    const results = Array.from({ length: 32 }, (_, i) =>
      makeRoute('KSEA', `KY${i.toString().padStart(2, '0')}`, i / 100)
    )
    renderWithSuspense(<ResultsBar results={results} airportIcao="KSEA" />)
    const el = screen.getByTestId(/hc-results-/)
    const data = JSON.parse(el.textContent ?? '[]') as Array<{ y: number }>
    expect(data).toHaveLength(30)
    // Top entry should be the highest on_time_ratio (index 31 → 31%)
    expect(data[0].y).toBeCloseTo(31, 1)
    // Second entry should be index 30 → 30%
    expect(data[1].y).toBeCloseTo(30, 1)
    // Values should be strictly non-increasing
    for (let i = 1; i < data.length; i++) {
      expect(data[i].y).toBeLessThanOrEqual(data[i - 1].y)
    }
  })
})
