import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useEscape } from '../../hooks/useEscape'
import { useClickOutside } from '../../hooks/useClickOutside'
import {
  queryRouteDaily,
  queryRouteCarriers,
  queryRouteReasons,
  type DailyRouteCancellation,
  type CarrierRouteCancellation,
  type RouteCancellationReason,
} from '../../db/queries'
import { ChartSpinner } from '../CancellationSection/ChartSpinner'
import './RoutePanel.css'

const RoutePanelDailySparkline = lazy(() =>
  import('./RoutePanelDailySparkline').then(m => ({ default: m.RoutePanelDailySparkline }))
)
const RoutePanelCarrierBreakdown = lazy(() =>
  import('./RoutePanelCarrierBreakdown').then(m => ({ default: m.RoutePanelCarrierBreakdown }))
)
const RoutePanelReasonMix = lazy(() =>
  import('./RoutePanelReasonMix').then(m => ({ default: m.RoutePanelReasonMix }))
)

interface Props {
  airportIcao: string
  origin: string
  destination: string
  onClose: () => void
}

interface PanelState {
  daily: DailyRouteCancellation[] | { error: string }
  carriers: CarrierRouteCancellation[] | { error: string }
  reasons: RouteCancellationReason[] | { error: string }
  loading: boolean
}

export function RoutePanel({ airportIcao, origin, destination, onClose }: Props) {
  const panelRef = useRef<HTMLElement>(null)
  const closeBtnRef = useRef<HTMLButtonElement>(null)

  const [state, setState] = useState<PanelState>({
    daily: [],
    carriers: [],
    reasons: [],
    loading: true,
  })

  useEscape(onClose)
  useClickOutside(panelRef, onClose)

  // Focus management: steal focus on mount, restore on unmount.
  // Capture trigger inside the effect so concurrent renders don't snapshot
  // stale focus state.
  useEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    closeBtnRef.current?.focus()
    return () => {
      trigger?.focus()
    }
  }, [])

  // Focus trap: Tab / Shift-Tab cycle stays inside the panel (WCAG 2.1.2).
  useEffect(() => {
    const node = panelRef.current
    if (!node) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      const focusables = node.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input, [tabindex]:not([tabindex="-1"])'
      )
      if (focusables.length === 0) return
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const active = document.activeElement
      if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }
    node.addEventListener('keydown', onKey)
    return () => node.removeEventListener('keydown', onKey)
  }, [])

  // Load all 3 queries in parallel; one failure doesn't block the others
  useEffect(() => {
    setState(s => ({ ...s, loading: true }))
    let cancelled = false
    Promise.allSettled([
      queryRouteDaily(airportIcao, origin, destination),
      queryRouteCarriers(airportIcao, origin, destination),
      queryRouteReasons(airportIcao, origin, destination),
    ]).then(([dailyResult, carriersResult, reasonsResult]) => {
      if (cancelled) return
      setState({
        daily: dailyResult.status === 'fulfilled'
          ? dailyResult.value
          : { error: 'Couldn\'t load daily timeliness.' },
        carriers: carriersResult.status === 'fulfilled'
          ? carriersResult.value
          : { error: 'Couldn\'t load carrier breakdown.' },
        reasons: reasonsResult.status === 'fulfilled'
          ? reasonsResult.value
          : { error: 'Couldn\'t load cancellation reasons.' },
        loading: false,
      })
    })
    return () => { cancelled = true }
  }, [airportIcao, origin, destination])

  return (
    <div className="route-panel-backdrop">
      <aside
        ref={panelRef}
        className="route-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="route-panel-heading"
      >
        <header className="route-panel-header">
          <h3 id="route-panel-heading">{origin} → {destination}</h3>
          <button
            ref={closeBtnRef}
            className="route-panel-close"
            onClick={onClose}
            aria-label="Close panel"
          >
            ×
          </button>
        </header>

        {state.loading ? (
          <p className="route-panel-loading" aria-busy="true">Loading route data…</p>
        ) : (
          <>
            <Suspense fallback={<ChartSpinner label="Loading daily chart…" />}>
              <RoutePanelDailySparkline data={state.daily} />
            </Suspense>
            <Suspense fallback={<ChartSpinner label="Loading carrier chart…" />}>
              <RoutePanelCarrierBreakdown data={state.carriers} />
            </Suspense>
            <Suspense fallback={<ChartSpinner label="Loading reasons chart…" />}>
              <RoutePanelReasonMix data={state.reasons} />
            </Suspense>
          </>
        )}
      </aside>
    </div>
  )
}
