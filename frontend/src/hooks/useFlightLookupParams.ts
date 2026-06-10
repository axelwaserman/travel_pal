import { useCallback, useEffect, useState } from 'react'

export type FlightLookupParams = {
  tab: 'airports' | 'carriers'
  q: string
  sort: 'on_time_desc' | 'on_time_asc' | 'delay_asc' | 'delay_desc' | 'volume_desc' | 'volume_asc' | 'volatility_asc'
  min: number
  route: string | null
}

const DEFAULT: FlightLookupParams = {
  tab: 'airports',
  q: '',
  sort: 'on_time_desc',
  min: 1,
  route: null,
}

function read(): FlightLookupParams {
  const sp = new URLSearchParams(window.location.search)
  return {
    tab: (sp.get('tab') === 'carriers' ? 'carriers' : 'airports'),
    q: sp.get('q') ?? '',
    sort: (sp.get('sort') ?? 'on_time_desc') as FlightLookupParams['sort'],
    min: Math.max(1, Math.min(1000, Number(sp.get('min') ?? 1))),
    route: sp.get('route'),
  }
}

function write(p: Partial<FlightLookupParams>) {
  const sp = new URLSearchParams(window.location.search)
  Object.entries(p).forEach(([k, v]) => {
    if (
      v == null ||
      v === '' ||
      (k === 'min' && v === 1) ||
      (k === 'tab' && v === 'airports') ||
      (k === 'sort' && v === 'on_time_desc')
    ) {
      sp.delete(k)
    } else {
      sp.set(k, String(v))
    }
  })
  const next = sp.toString()
  const url = `${window.location.pathname}${next ? '?' + next : ''}`
  window.history.replaceState({}, '', url)
}

// Re-export DEFAULT so callers can reference the canonical defaults if needed.
export { DEFAULT as FLIGHT_LOOKUP_DEFAULTS }

export function useFlightLookupParams() {
  const [params, setParams] = useState<FlightLookupParams>(read)

  useEffect(() => {
    const onPop = () => setParams(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const update = useCallback((patch: Partial<FlightLookupParams>) => {
    write(patch)
    setParams(read())
  }, [])

  return [params, update] as const
}
