import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import {
  queryAirportSearch,
  queryCarrierSearch,
  type CarrierCancellation,
  type RouteTimelinessWithAirportName,
} from '../../db/queries'
import { pct, fmt, NULL_PLACEHOLDER } from '../../db/format'
import { ChartSpinner } from '../CancellationSection/ChartSpinner'
import {
  useFlightLookupParams,
  type FlightLookupParams,
} from '../../hooks/useFlightLookupParams'
import SearchTabs from './SearchTabs'
import SortBar from './SortBar'
import MinFlightsSlider from './MinFlightsSlider'
import './FlightLookup.css'

const ResultsBar = lazy(() =>
  import('./ResultsBar').then(m => ({ default: m.ResultsBar }))
)

interface Props {
  airportIcao: string
}

// ---------------------------------------------------------------------------
// Sorting helpers
// ---------------------------------------------------------------------------

type AirportResult = RouteTimelinessWithAirportName
type CarrierResult = CarrierCancellation

function sortAirportResults(
  rows: AirportResult[],
  sort: FlightLookupParams['sort']
): AirportResult[] {
  const copy = rows.slice()
  switch (sort) {
    case 'on_time_desc':
      return copy.sort((a, b) => (b.on_time_ratio ?? -1) - (a.on_time_ratio ?? -1))
    case 'on_time_asc':
      return copy.sort((a, b) => (a.on_time_ratio ?? Infinity) - (b.on_time_ratio ?? Infinity))
    case 'delay_asc':
      return copy.sort((a, b) => (a.avg_delay_minutes ?? Infinity) - (b.avg_delay_minutes ?? Infinity))
    case 'delay_desc':
      return copy.sort((a, b) => (b.avg_delay_minutes ?? -1) - (a.avg_delay_minutes ?? -1))
    case 'volume_desc':
      return copy.sort((a, b) => b.total_flights - a.total_flights)
    case 'volume_asc':
      return copy.sort((a, b) => a.total_flights - b.total_flights)
    case 'volatility_asc':
      return copy.sort((a, b) => (a.delay_volatility ?? Infinity) - (b.delay_volatility ?? Infinity))
    default:
      return copy
  }
}

function sortCarrierResults(
  rows: CarrierResult[],
  sort: FlightLookupParams['sort']
): CarrierResult[] {
  const copy = rows.slice()
  switch (sort) {
    case 'on_time_desc':
      // Carriers: lower cancellation = more on-time
      return copy.sort((a, b) => (a.cancellation_rate ?? Infinity) - (b.cancellation_rate ?? Infinity))
    case 'on_time_asc':
      return copy.sort((a, b) => (b.cancellation_rate ?? -1) - (a.cancellation_rate ?? -1))
    case 'volume_desc':
      return copy.sort((a, b) => b.total_scheduled - a.total_scheduled)
    case 'volume_asc':
      return copy.sort((a, b) => a.total_scheduled - b.total_scheduled)
    default:
      return copy
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FlightLookup({ airportIcao }: Props) {
  const [params, setParams] = useFlightLookupParams()
  const [inputValue, setInputValue] = useState(params.q)

  // Raw results from the last query — typed union depending on active tab
  const [airportResults, setAirportResults] = useState<AirportResult[]>([])
  const [carrierResults, setCarrierResults] = useState<CarrierResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Keep local input in sync when params.q changes externally (e.g. popstate)
  useEffect(() => {
    setInputValue(params.q)
  }, [params.q])

  // --------------------------------------------------------------------------
  // Query effect: fires when tab or search term changes
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!params.q.trim()) {
      setAirportResults([])
      setCarrierResults([])
      return
    }

    setLoading(true)
    setError(null)

    const q = params.q.trim()

    if (params.tab === 'airports') {
      queryAirportSearch(airportIcao, q)
        .then(data => setAirportResults(data))
        .catch(() => setError('Failed to load flight data. Check that the pipeline has run.'))
        .finally(() => setLoading(false))
    } else {
      queryCarrierSearch(airportIcao, q)
        .then(data => setCarrierResults(data))
        .catch(() => setError('Failed to load flight data. Check that the pipeline has run.'))
        .finally(() => setLoading(false))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.tab, params.q])

  // --------------------------------------------------------------------------
  // Client-side sort + filter via useMemo — no re-query on sort/min change
  // --------------------------------------------------------------------------

  const visibleAirportResults = useMemo(() => {
    const sorted = sortAirportResults(airportResults, params.sort)
    return sorted.filter(r => r.total_flights >= params.min)
  }, [airportResults, params.sort, params.min])

  const visibleCarrierResults = useMemo(() => {
    const sorted = sortCarrierResults(carrierResults, params.sort)
    return sorted.filter(r => r.total_scheduled >= params.min)
  }, [carrierResults, params.sort, params.min])

  // --------------------------------------------------------------------------
  // Handlers
  // --------------------------------------------------------------------------

  function handleSearch() {
    const trimmed = inputValue.trim()
    if (!trimmed) return
    setParams({ q: trimmed })
  }

  function handleTabChange(tab: 'airports' | 'carriers') {
    // Clear results and reset min when switching tabs — volume scales differ
    setAirportResults([])
    setCarrierResults([])
    setParams({ tab, min: 1 })
  }

  // --------------------------------------------------------------------------
  // Derived state for empty-state messages
  // --------------------------------------------------------------------------

  const isAirportTab = params.tab === 'airports'
  const rawCount = isAirportTab ? airportResults.length : carrierResults.length
  const visibleCount = isAirportTab ? visibleAirportResults.length : visibleCarrierResults.length

  function renderEmptyState() {
    if (!params.q.trim()) {
      return (
        <p className="lookup-empty">
          Type an airport (KJFK / JFK) or carrier (DAL / Delta) to begin.
        </p>
      )
    }
    if (rawCount === 0 && !loading) {
      return (
        <p className="lookup-empty">
          No routes found for <code>{params.q}</code>. Try a different ICAO/IATA code or carrier name.
        </p>
      )
    }
    if (rawCount > 0 && visibleCount === 0) {
      return (
        <p className="lookup-empty">
          0 of {rawCount} results meet ≥{params.min} flights threshold. Lower the slider.
        </p>
      )
    }
    return null
  }

  // --------------------------------------------------------------------------
  // Result card renders
  // --------------------------------------------------------------------------

  function renderAirportCard(r: AirportResult) {
    return (
      <article key={`${r.origin_icao}-${r.destination_icao}`} className="result-card">
        <h3>{r.origin_icao} → {r.destination_icao}</h3>
        <dl>
          <dt>On-time ratio</dt>
          <dd>{pct(r.on_time_ratio)}</dd>
          <dt>Avg delay</dt>
          <dd>{r.avg_delay_minutes == null ? NULL_PLACEHOLDER : `${fmt(r.avg_delay_minutes)} min`}</dd>
          <dt>Total flights</dt>
          <dd>{r.total_flights.toLocaleString()}</dd>
        </dl>
      </article>
    )
  }

  function renderCarrierCard(r: CarrierResult) {
    return (
      <article key={`${r.carrier_icao}-${r.origin_icao}`} className="result-card">
        <h3>{r.carrier_icao}</h3>
        <dl>
          <dt>Carrier</dt>
          <dd>{r.carrier_name}</dd>
          <dt>Cancellation rate</dt>
          <dd>{pct(r.cancellation_rate)}</dd>
          <dt>Total scheduled</dt>
          <dd>{r.total_scheduled.toLocaleString()}</dd>
        </dl>
      </article>
    )
  }

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <section className="flight-lookup" aria-labelledby="lookup-heading">
      <h2 id="lookup-heading">Flight Lookup</h2>

      <SearchTabs value={params.tab} onChange={handleTabChange} />

      <div className="lookup-input-row">
        <input
          type="text"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Route or airport ICAO (e.g. KLAX)"
          aria-label="Flight route or airport"
        />
        <button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>

      <div className="lookup-controls-row">
        <SortBar value={params.sort} onChange={sort => setParams({ sort })} />
        <MinFlightsSlider
          value={params.min}
          onChange={min => setParams({ min })}
        />
      </div>

      {error && <p className="lookup-error" role="alert">{error}</p>}

      {isAirportTab && visibleAirportResults.length > 0 && (
        <Suspense fallback={<ChartSpinner label="Loading results chart…" />}>
          <ResultsBar results={visibleAirportResults} airportIcao={airportIcao} />
        </Suspense>
      )}

      {renderEmptyState()}

      <div className="results-grid">
        {isAirportTab
          ? visibleAirportResults.map(r => renderAirportCard(r))
          : visibleCarrierResults.map(r => renderCarrierCard(r))
        }
      </div>
    </section>
  )
}
