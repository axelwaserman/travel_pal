import { useEffect, useState } from 'react'
import {
  CarrierCancellation,
  RouteCancellation,
  queryCarrierCancellations,
  queryRouteCancellations,
} from '../../db/queries'
import { fmtDate } from '../../db/format'
import CarrierBar from './CarrierBar'
import RouteBar from './RouteBar'
import './CancellationSection.css'

interface Props {
  airportIcao: string
}

interface Data {
  carriers: CarrierCancellation[]
  routes: RouteCancellation[]
}

export default function CancellationSection({ airportIcao }: Props) {
  const [data, setData] = useState<Data | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    Promise.all([
      queryCarrierCancellations(airportIcao),
      queryRouteCancellations(airportIcao),
    ])
      .then(([carriers, routes]) => {
        if (isMounted) setData({ carriers, routes })
      })
      .catch(() => {
        if (isMounted) setError('Failed to load cancellation data.')
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [airportIcao])

  if (loading) {
    return (
      <section className="cancellation-section" aria-labelledby="cancel-heading">
        <h2 id="cancel-heading">Cancellations — {airportIcao}</h2>
        <p aria-busy="true">Loading cancellation data…</p>
      </section>
    )
  }
  if (error) {
    return (
      <section className="cancellation-section" aria-labelledby="cancel-heading">
        <h2 id="cancel-heading">Cancellations — {airportIcao}</h2>
        <p role="alert">{error}</p>
      </section>
    )
  }
  if (!data || (data.carriers.length === 0 && data.routes.length === 0)) {
    return (
      <section className="cancellation-section" aria-labelledby="cancel-heading">
        <h2 id="cancel-heading">Cancellations — {airportIcao}</h2>
        <p>No cancellation data available. Run the BTS pipeline first.</p>
      </section>
    )
  }

  const sample = data.carriers[0] ?? data.routes[0]
  const periodCaption = sample
    ? `BTS data: ${fmtDate(sample.period_start)} – ${fmtDate(sample.period_end)}`
    : null

  return (
    <section className="cancellation-section" aria-labelledby="cancel-heading">
      <h2 id="cancel-heading">Cancellations — {airportIcao}</h2>
      {periodCaption && <p className="period-caption">{periodCaption}</p>}
      <div className="cancellation-grid">
        <div className="chart-wrap">
          <CarrierBar airportIcao={airportIcao} carriers={data.carriers} />
        </div>
        <div className="chart-wrap">
          <RouteBar airportIcao={airportIcao} routes={data.routes} />
        </div>
      </div>
    </section>
  )
}
