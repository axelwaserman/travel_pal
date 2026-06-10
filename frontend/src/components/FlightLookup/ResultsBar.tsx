import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import type { RouteTimeliness } from '../../db/schemas'

// ResultsBar only needs origin_icao, destination_icao, on_time_ratio, and
// total_flights — accept the base type so it works both before and after the
// Task 7 upgrade to RouteTimelinessWithAirportName.
type RouteRow = Pick<
  RouteTimeliness,
  'origin_icao' | 'destination_icao' | 'on_time_ratio' | 'total_flights'
>
type RouteWithRatio = RouteRow & { on_time_ratio: number }

interface Props {
  results: readonly RouteRow[]
  airportIcao: string
}

export function ResultsBar({ results, airportIcao }: Props) {
  if (results.length === 0) return null

  const data = results
    .slice()
    .filter((r): r is RouteWithRatio => r.on_time_ratio !== null)
    .slice(0, 30)
    .map(r => ({
      name: `${r.origin_icao} → ${r.destination_icao}`,
      y: r.on_time_ratio * 100,
      total: r.total_flights,
    }))

  const options: Highcharts.Options = {
    chart: { type: 'column', backgroundColor: 'transparent', height: 280 },
    title: { text: `Results — ${airportIcao}` },
    xAxis: {
      categories: data.map(d => d.name),
      labels: {
        style: { color: 'currentColor' },
        rotation: -45,
      },
    },
    yAxis: {
      title: { text: 'On-time ratio (%)' },
      labels: { style: { color: 'currentColor' } },
      min: 0,
      max: 100,
    },
    legend: { enabled: false },
    credits: { enabled: false },
    tooltip: {
      pointFormat: '<b>{point.y:.1f}%</b> on time<br/>{point.total:,} total flights',
    },
    series: [
      {
        type: 'column',
        name: 'On-time ratio',
        data,
        color: 'oklch(56% 0.19 250)',
      },
    ],
  }

  return <HighchartsReact highcharts={Highcharts} options={options} />
}
