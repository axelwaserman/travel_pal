import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

vi.mock('highcharts', () => ({ default: {} }))
vi.mock('highcharts-react-official', () => ({
  default: () => <div data-testid="highcharts-stub" />,
}))

const { RoutePanelCarrierBreakdown } = await import('./RoutePanelCarrierBreakdown')

describe('RoutePanelCarrierBreakdown', () => {
  it('renders a chart when given an array of data', () => {
    const data = [
      {
        origin_icao: 'KJFK',
        destination_icao: 'KLAX',
        carrier_icao: 'DAL',
        carrier_name: 'Delta',
        total_scheduled: 100,
        cancelled: 5,
        cancellation_rate: 0.05,
        period_start: '2024-01-01',
        period_end: '2024-12-31',
      },
    ]
    render(<RoutePanelCarrierBreakdown data={data} />)
    expect(screen.getByTestId('highcharts-stub')).toBeInTheDocument()
  })

  it('shows empty state when given an empty array', () => {
    render(<RoutePanelCarrierBreakdown data={[]} />)
    expect(screen.getByText(/no data for this route/i)).toBeInTheDocument()
  })

  it('shows error banner when given an error object', () => {
    render(<RoutePanelCarrierBreakdown data={{ error: 'carriers failed' }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('carriers failed')
  })
})
