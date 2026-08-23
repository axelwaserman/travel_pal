import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { type DailyRouteCancellation } from '../../db/queries'

interface Props {
  data: DailyRouteCancellation[] | { error: string }
}

export function RoutePanelDailySparkline({ data }: Props) {
  if (!Array.isArray(data)) {
    return (
      <div className="route-panel-section">
        <h4>Daily Cancellations</h4>
        <p className="route-panel-error" role="alert">{data.error}</p>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="route-panel-section">
        <h4>Daily Cancellations</h4>
        <p className="route-panel-empty">No data for this route.</p>
      </div>
    )
  }

  const chartData = data
    .filter(d => d.cancellation_rate !== null)
    .map(d => ({
      x: typeof d.flight_date === 'string'
        ? new Date(d.flight_date).getTime()
        : typeof d.flight_date === 'number'
          ? d.flight_date
          : (d.flight_date as Date).getTime(),
      y: (d.cancellation_rate as number) * 100,
    }))

  const options: Highcharts.Options = {
    chart: {
      type: 'spline',
      backgroundColor: 'transparent',
      height: 160,
      margin: [10, 10, 30, 40],
    },
    title: { text: undefined },
    xAxis: {
      type: 'datetime',
      labels: { style: { color: 'currentColor', fontSize: '10px' } },
    },
    yAxis: {
      title: { text: null },
      labels: {
        style: { color: 'currentColor', fontSize: '10px' },
        format: '{value}%',
      },
      min: 0,
    },
    legend: { enabled: false },
    credits: { enabled: false },
    tooltip: { pointFormat: '<b>{point.y:.1f}%</b> cancelled' },
    series: [
      {
        type: 'spline',
        name: 'Cancellation rate',
        data: chartData,
        color: 'oklch(56% 0.19 25)',
        lineWidth: 2,
        marker: { radius: 2 },
      },
    ],
  }

  return (
    <div className="route-panel-section">
      <h4>Daily Cancellations</h4>
      <HighchartsReact highcharts={Highcharts} options={options} />
    </div>
  )
}
