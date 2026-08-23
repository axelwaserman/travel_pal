import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { type RouteCancellationReason } from '../../db/queries'

interface Props {
  data: RouteCancellationReason[] | { error: string }
}

// Colour palette keyed by reason string for consistent colouring
const REASON_COLOURS: Record<string, string> = {
  'Air Carrier': 'oklch(56% 0.19 25)',
  'Weather': 'oklch(56% 0.19 250)',
  'National Air System': 'oklch(56% 0.19 145)',
  'Security': 'oklch(56% 0.19 320)',
  'Other / Unknown': 'oklch(60% 0.04 0)',
}

export function RoutePanelReasonMix({ data }: Props) {
  if (!Array.isArray(data)) {
    return (
      <div className="route-panel-section">
        <h4>Cancellation Reasons</h4>
        <p className="route-panel-error" role="alert">{data.error}</p>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="route-panel-section">
        <h4>Cancellation Reasons</h4>
        <p className="route-panel-empty">No data for this route.</p>
      </div>
    )
  }

  const chartData = data
    .filter(d => d.reason_share !== null)
    .sort((a, b) => (b.reason_share as number) - (a.reason_share as number))
    .map(d => ({
      name: d.reason,
      y: (d.reason_share as number) * 100,
      count: d.cancelled_count,
      color: REASON_COLOURS[d.reason] ?? 'oklch(60% 0.04 0)',
    }))

  const options: Highcharts.Options = {
    chart: { type: 'pie', backgroundColor: 'transparent', height: 200 },
    title: { text: undefined },
    legend: {
      enabled: true,
      itemStyle: { color: 'currentColor', fontSize: '11px', fontWeight: 'normal' },
    },
    credits: { enabled: false },
    tooltip: {
      pointFormat: '<b>{point.y:.1f}%</b> ({point.count:,} flights)',
    },
    plotOptions: {
      pie: {
        dataLabels: { enabled: false },
        showInLegend: true,
      },
    },
    series: [
      {
        type: 'pie',
        name: 'Reason share',
        data: chartData,
      },
    ],
  }

  return (
    <div className="route-panel-section">
      <h4>Cancellation Reasons</h4>
      <HighchartsReact highcharts={Highcharts} options={options} />
    </div>
  )
}
