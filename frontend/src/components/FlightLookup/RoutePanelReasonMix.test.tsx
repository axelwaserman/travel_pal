import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

vi.mock('highcharts', () => ({ default: {} }))
vi.mock('highcharts-react-official', () => ({
  default: () => <div data-testid="highcharts-stub" />,
}))

const { RoutePanelReasonMix } = await import('./RoutePanelReasonMix')

describe('RoutePanelReasonMix', () => {
  it('renders a chart when given an array of data', () => {
    const data = [
      {
        origin_icao: 'KJFK',
        destination_icao: 'KLAX',
        reason: 'Weather' as const,
        cancelled_count: 10,
        reason_share: 0.5,
      },
    ]
    render(<RoutePanelReasonMix data={data} />)
    expect(screen.getByTestId('highcharts-stub')).toBeInTheDocument()
  })

  it('shows empty state when given an empty array', () => {
    render(<RoutePanelReasonMix data={[]} />)
    expect(screen.getByText(/no data for this route/i)).toBeInTheDocument()
  })

  it('shows error banner when given an error object', () => {
    render(<RoutePanelReasonMix data={{ error: 'reasons failed' }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('reasons failed')
  })
})
