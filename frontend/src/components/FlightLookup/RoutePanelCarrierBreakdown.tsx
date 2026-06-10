import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { type CarrierRouteCancellation } from '../../db/queries'

interface Props {
  data: CarrierRouteCancellation[] | { error: string }
}

type RowWithRate = CarrierRouteCancellation & { cancellation_rate: number }

export function RoutePanelCarrierBreakdown({ data }: Props) {
  if (!Array.isArray(data)) {
    return (
      <div className="route-panel-section">
        <h4>Carrier Breakdown</h4>
        <p className="route-panel-error" role="alert">{data.error}</p>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="route-panel-section">
        <h4>Carrier Breakdown</h4>
        <p className="route-panel-empty">No data for this route.</p>
      </div>
    )
  }

  const chartData = data
    .filter((d): d is RowWithRate => d.cancellation_rate !== null)
    .sort((a, b) => b.cancellation_rate - a.cancellation_rate)
    .map(d => ({
      name: d.carrier_name,
      y: d.cancellation_rate * 100,
      total: d.total_scheduled,
      cancelled: d.cancelled,
    }))

  const options: Highcharts.Options = {
    chart: { type: 'bar', backgroundColor: 'transparent', height: Math.max(100, chartData.length * 28 + 40) },
    title: { text: undefined },
    xAxis: {
      categories: chartData.map(d => d.name),
      labels: { style: { color: 'currentColor', fontSize: '11px' } },
    },
    yAxis: {
      title: { text: null },
      labels: { style: { color: 'currentColor', fontSize: '10px' }, format: '{value}%' },
    },
    legend: { enabled: false },
    credits: { enabled: false },
    tooltip: {
      pointFormat: '<b>{point.y:.2f}%</b><br/>{point.cancelled:,} of {point.total:,} cancelled',
    },
    series: [
      {
        type: 'bar',
        name: 'Cancellation rate',
        data: chartData,
        colorByPoint: false,
        color: 'oklch(56% 0.19 25)',
      },
    ],
  }

  return (
    <div className="route-panel-section">
      <h4>Carrier Breakdown</h4>
      <HighchartsReact highcharts={Highcharts} options={options} />
    </div>
  )
}
