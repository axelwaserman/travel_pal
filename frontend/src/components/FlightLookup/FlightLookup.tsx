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
import { RoutePanel } from './RoutePanel'
import './FlightLookup.css'

// Sort values available when the Carriers tab is active.
// delay/volatility fields don't exist on CarrierCancellation rows.
const CARRIER_SORT_VALUES = ['volume_desc', 'volume_asc'] as const

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
  const [controlsOpen, setControlsOpen] = useState(false)

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
    // Fix 3: always clear a stale error even when the query is empty.
    setError(null)

    if (!params.q.trim()) {
      setAirportResults([])
      setCarrierResults([])
      return
    }

    // Fix 1: cancellation guard — if this effect's cleanup fires (because a
    // newer query superseded this one), none of the state setters below will run.
    let ignored = false

    setLoading(true)

    const promise = params.tab === 'airports'
      ? queryAirportSearch(airportIcao, params.q.trim())
      : queryCarrierSearch(airportIcao, params.q.trim())

    promise
      .then(data => {
        if (ignored) return
        if (params.tab === 'airports') setAirportResults(data as RouteTimelinessWithAirportName[])
        else setCarrierResults(data as CarrierCancellation[])
      })
      .catch(() => {
        if (ignored) return
        setError('Failed to load. Run the pipeline (just run-pipeline).')
      })
      .finally(() => {
        if (ignored) return
        setLoading(false)
      })

    return () => { ignored = true }
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
    // Clear results and reset min when switching tabs — volume scales differ.
    // When switching to carriers, also reset sort to volume_desc because the
    // carrier sort subset doesn't include delay/volatility/on-time options.
    setAirportResults([])
    setCarrierResults([])
    if (tab === 'carriers') {
      setParams({ tab, min: 1, sort: 'volume_desc' })
    } else {
      setParams({ tab, min: 1 })
    }
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
      <article
        key={`${r.origin_icao}-${r.destination_icao}`}
        className="result-card result-card--clickable"
        onClick={() => setParams({ route: `${r.origin_icao}-${r.destination_icao}` })}
        tabIndex={0}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setParams({ route: `${r.origin_icao}-${r.destination_icao}` })
          }
        }}
      >
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

      <button
        className="lookup-controls-toggle"
        aria-expanded={controlsOpen}
        aria-controls="lookup-controls"
        onClick={() => setControlsOpen(o => !o)}
      >
        {controlsOpen ? 'Hide filters ▲' : 'Filters & sort ▼'}
      </button>

      <div
        id="lookup-controls"
        className={`lookup-controls-row${controlsOpen ? ' lookup-controls-row--open' : ''}`}
      >
        <SortBar
          value={params.sort}
          onChange={sort => setParams({ sort })}
          availableValues={params.tab === 'carriers' ? CARRIER_SORT_VALUES : undefined}
        />
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

      {(() => {
        const routeParts = params.route ? params.route.split(/-(.+)/).slice(0, 2) : null
        const validRoute = routeParts && routeParts[0]?.length >= 3 && routeParts[1]?.length >= 3
        if (!validRoute) return null
        return (
          <RoutePanel
            airportIcao={airportIcao}
            origin={routeParts[0]}
            destination={routeParts[1]}
            onClose={() => setParams({ route: null })}
          />
        )
      })()}
    </section>
  )
}
