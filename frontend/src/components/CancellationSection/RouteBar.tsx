import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { RouteCancellation } from '../../db/queries'

interface Props {
  airportIcao: string
  routes: readonly RouteCancellation[]
}

export default function RouteBar({ airportIcao, routes }: Props) {
  const data = routes
    .slice()
    .sort((a, b) => b.cancellation_rate - a.cancellation_rate)
    .slice(0, 10)
    .map(r => ({
      name: `${r.origin_icao} → ${r.destination_icao}`,
      y: r.cancellation_rate * 100,
      total: r.total_scheduled,
      cancelled: r.cancelled,
    }))

  const options: Highcharts.Options = {
    chart: { type: 'bar', backgroundColor: 'transparent', height: 360 },
    title: { text: `Routes — ${airportIcao}` },
    xAxis: {
      categories: data.map(d => d.name),
      labels: { style: { color: 'currentColor' } },
    },
    yAxis: {
      title: { text: 'Cancellation rate (%)' },
      labels: { style: { color: 'currentColor' } },
    },
    legend: { enabled: false },
    credits: { enabled: false },
    tooltip: {
      pointFormat:
        '<b>{point.y:.2f}%</b><br/>{point.cancelled:,} of {point.total:,} cancelled',
    },
    series: [
      {
        type: 'bar',
        name: 'Cancellation rate',
        data,
        color: 'oklch(56% 0.19 25)',
      },
    ],
  }

  return <HighchartsReact highcharts={Highcharts} options={options} />
}
