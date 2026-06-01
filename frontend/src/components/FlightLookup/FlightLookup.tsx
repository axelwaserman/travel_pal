import { useState } from 'react'
import { queryFlightLookup, RouteTimeliness } from '../../db/queries'
import './FlightLookup.css'

interface Props {
  airportIcao: string
}

export default function FlightLookup({ airportIcao }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<RouteTimeliness[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSearch() {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await queryFlightLookup(airportIcao, query.trim())
      setResults(data)
    } catch {
      setError('Failed to load flight data. Check that the pipeline has run.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="flight-lookup" aria-labelledby="lookup-heading">
      <h2 id="lookup-heading">Flight Lookup</h2>
      <div className="lookup-input-row">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Route or airport ICAO (e.g. KLAX)"
          aria-label="Flight route or airport"
        />
        <button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>
      {error && <p className="lookup-error" role="alert">{error}</p>}
      <div className="results-grid">
        {results.map(r => (
          <article key={`${r.origin_icao}-${r.destination_icao}`} className="result-card">
            <h3>{r.origin_icao} → {r.destination_icao}</h3>
            <dl>
              <dt>On-time ratio</dt>
              <dd>{(r.on_time_ratio * 100).toFixed(1)}%</dd>
              <dt>Avg delay</dt>
              <dd>{r.avg_delay_minutes} min</dd>
              <dt>Total flights</dt>
              <dd>{r.total_flights.toLocaleString()}</dd>
            </dl>
          </article>
        ))}
      </div>
    </section>
  )
}
