import { useEffect, useState } from 'react'
import { queryDailyTimeliness, DailyTimeliness } from '../../db/queries'
import './TimelinessDashboard.css'

interface Props {
  airportIcao: string
}

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`
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

  const avgOnTime = data.reduce((sum, d) => sum + d.on_time_ratio, 0) / data.length
  const avgDelay = data.reduce((sum, d) => sum + d.avg_delay_minutes, 0) / data.length
  const avgVolatility = data.reduce((sum, d) => sum + d.delay_volatility, 0) / data.length

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
          <span className="metric-value">{avgDelay.toFixed(1)} min</span>
          <span className="metric-sub">vs. route median</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Delay volatility</span>
          <span className="metric-value">{avgVolatility.toFixed(1)} min</span>
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
              <td>{d.avg_delay_minutes.toFixed(1)}</td>
              <td>{d.delay_volatility.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
