import { useEffect, useState } from 'react'
import { queryDailyTimeliness, DailyTimeliness } from '../../db/queries'
import { pct, fmt } from '../../db/format'
import './TimelinessDashboard.css'

interface Props {
  airportIcao: string
}

type NumericKey = {
  [K in keyof DailyTimeliness]: DailyTimeliness[K] extends number | null ? K : never
}[keyof DailyTimeliness]

function mean(rows: readonly DailyTimeliness[], key: NumericKey): number | null {
  const nums = rows
    .map(r => r[key])
    .filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  if (nums.length === 0) return null
  return nums.reduce((s, n) => s + n, 0) / nums.length
}

export default function TimelinessDashboard({ airportIcao }: Props) {
  const [data, setData] = useState<DailyTimeliness[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    queryDailyTimeliness(airportIcao)
      .then(data => { if (isMounted) setData(data) })
      .catch(() => { if (isMounted) setError('Failed to load timeliness data.') })
      .finally(() => { if (isMounted) setLoading(false) })
    return () => { isMounted = false }
  }, [airportIcao])

  if (loading) return <p aria-busy="true">Loading timeliness data…</p>
  if (error) return <p role="alert">{error}</p>
  if (data.length === 0) return <p>No data available. Run the pipeline first.</p>

  const avgOnTime = mean(data, 'on_time_ratio')
  const avgDelay = mean(data, 'avg_delay_minutes')
  const avgVolatility = mean(data, 'delay_volatility')

  return (
    <section className="timeliness-dashboard" aria-labelledby="dashboard-heading">
      <h2 id="dashboard-heading">Historic Timeliness — {airportIcao}</h2>
      <div className="metric-row">
        <div className="metric-card">
          <span className="metric-label">On-time arrival ratio</span>
          <span className="metric-value">{pct(avgOnTime)}</span>
          <span className="metric-sub">≤15 min variance</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Average delay</span>
          <span className="metric-value">{fmt(avgDelay)} min</span>
          <span className="metric-sub">vs. route median</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Delay volatility</span>
          <span className="metric-value">{fmt(avgVolatility)} min</span>
          <span className="metric-sub">std dev of delay</span>
        </div>
      </div>
      <table className="daily-table" aria-label="Daily timeliness breakdown">
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Flights</th>
            <th scope="col">On-time %</th>
            <th scope="col">Avg delay (min)</th>
            <th scope="col">Volatility (min)</th>
          </tr>
        </thead>
        <tbody>
          {data.map(d => (
            <tr key={d.flight_date}>
              <td>{d.flight_date}</td>
              <td>{d.total_flights.toLocaleString()}</td>
              <td>{pct(d.on_time_ratio)}</td>
              <td>{fmt(d.avg_delay_minutes)}</td>
              <td>{fmt(d.delay_volatility)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
