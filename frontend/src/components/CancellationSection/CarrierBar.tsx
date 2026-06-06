import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { CarrierCancellation } from '../../db/queries'

interface Props {
  airportIcao: string
  carriers: readonly CarrierCancellation[]
}

export default function CarrierBar({ airportIcao, carriers }: Props) {
  const data = carriers
    .slice()
    .sort((a, b) => b.cancellation_rate - a.cancellation_rate)
    .slice(0, 10)
    .map(c => ({
      name: c.carrier_name,
      y: c.cancellation_rate * 100,
      total: c.total_scheduled,
      cancelled: c.cancelled,
    }))

  const options: Highcharts.Options = {
    chart: { type: 'bar', backgroundColor: 'transparent', height: 360 },
    title: { text: `Carriers — ${airportIcao}` },
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
        colorByPoint: false,
        color: 'oklch(56% 0.19 25)',
      },
    ],
  }

  return <HighchartsReact highcharts={Highcharts} options={options} />
}
