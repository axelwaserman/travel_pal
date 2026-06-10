import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

// Mock Highcharts to avoid canvas/worker requirement in jsdom
vi.mock('highcharts', () => ({ default: {} }))
vi.mock('highcharts-react-official', () => ({
  default: () => <div data-testid="highcharts-stub" />,
}))

const { RoutePanelDailySparkline } = await import('./RoutePanelDailySparkline')

describe('RoutePanelDailySparkline', () => {
  it('renders a chart when given an array of data', () => {
    const data = [
      {
        flight_date: '2024-01-01',
        origin_icao: 'KJFK',
        total_flights: 10,
        avg_delay_minutes: 5,
        delay_volatility: 2,
        on_time_ratio: 0.8,
      },
    ]
    render(<RoutePanelDailySparkline data={data} />)
    expect(screen.getByTestId('highcharts-stub')).toBeInTheDocument()
  })

  it('shows empty state when given an empty array', () => {
    render(<RoutePanelDailySparkline data={[]} />)
    expect(screen.getByText(/no data for this route/i)).toBeInTheDocument()
  })

  it('shows error banner when given an error object', () => {
    render(<RoutePanelDailySparkline data={{ error: 'daily failed' }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('daily failed')
  })
})
