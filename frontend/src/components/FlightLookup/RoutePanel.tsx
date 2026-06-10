import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useEscape } from '../../hooks/useEscape'
import { useClickOutside } from '../../hooks/useClickOutside'
import {
  queryRouteDaily,
  queryRouteCarriers,
  queryRouteReasons,
  type DailyTimeliness,
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
  origin: string
  destination: string
  onClose: () => void
}

interface PanelState {
  daily: DailyTimeliness[] | { error: string }
  carriers: CarrierRouteCancellation[] | { error: string }
  reasons: RouteCancellationReason[] | { error: string }
  loading: boolean
}

export function RoutePanel({ origin, destination, onClose }: Props) {
  const panelRef = useRef<HTMLElement>(null)
  const closeBtnRef = useRef<HTMLButtonElement>(null)
  // Capture the element that triggered the panel before we steal focus
  const triggerRef = useRef<HTMLElement | null>(
    document.activeElement instanceof HTMLElement ? document.activeElement : null
  )

  const [state, setState] = useState<PanelState>({
    daily: [],
    carriers: [],
    reasons: [],
    loading: true,
  })

  useEscape(onClose)
  useClickOutside(panelRef, onClose)

  // Focus management: steal focus on mount, restore on unmount.
  // Capture the trigger element in a local variable so the cleanup closure
  // holds a stable reference even after the ref is updated.
  useEffect(() => {
    const trigger = triggerRef.current
    closeBtnRef.current?.focus()
    return () => {
      trigger?.focus()
    }
  }, [])

  // Load all 3 queries in parallel; one failure doesn't block the others
  useEffect(() => {
    let cancelled = false
    Promise.allSettled([
      queryRouteDaily(origin, destination),
      queryRouteCarriers(origin, destination),
      queryRouteReasons(origin, destination),
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
  }, [origin, destination])

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
