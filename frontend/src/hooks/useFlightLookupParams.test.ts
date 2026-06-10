import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useFlightLookupParams, type FlightLookupParams } from './useFlightLookupParams'

function setSearch(search: string) {
  window.history.replaceState({}, '', search ? `/?${search}` : '/')
}

describe('useFlightLookupParams', () => {
  beforeEach(() => {
    // reset to clean URL before each test
    window.history.replaceState({}, '', '/')
  })

  afterEach(() => {
    window.history.replaceState({}, '', '/')
  })

  it('returns defaults when URL has no params', () => {
    const { result } = renderHook(() => useFlightLookupParams())
    const [params] = result.current
    expect(params.tab).toBe('airports')
    expect(params.q).toBe('')
    expect(params.sort).toBe('on_time_desc')
    expect(params.min).toBe(1)
    expect(params.route).toBeNull()
  })

  it('reads tab=carriers from URL', () => {
    setSearch('tab=carriers')
    const { result } = renderHook(() => useFlightLookupParams())
    expect(result.current[0].tab).toBe('carriers')
  })

  it('reads q from URL', () => {
    setSearch('q=KLAX')
    const { result } = renderHook(() => useFlightLookupParams())
    expect(result.current[0].q).toBe('KLAX')
  })

  it('reads sort from URL', () => {
    setSearch('sort=delay_asc')
    const { result } = renderHook(() => useFlightLookupParams())
    expect(result.current[0].sort).toBe('delay_asc')
  })

  it('reads min from URL', () => {
    setSearch('min=250')
    const { result } = renderHook(() => useFlightLookupParams())
    expect(result.current[0].min).toBe(250)
  })

  it('clamps min to 1..1000', () => {
    setSearch('min=0')
    const { result: r1 } = renderHook(() => useFlightLookupParams())
    expect(r1.current[0].min).toBe(1)

    setSearch('min=9999')
    const { result: r2 } = renderHook(() => useFlightLookupParams())
    expect(r2.current[0].min).toBe(1000)
  })

  it('reads route from URL', () => {
    setSearch('route=KJFK-KLAX')
    const { result } = renderHook(() => useFlightLookupParams())
    expect(result.current[0].route).toBe('KJFK-KLAX')
  })

  it('update writes non-default values to URL', () => {
    const { result } = renderHook(() => useFlightLookupParams())
    act(() => {
      result.current[1]({ tab: 'carriers', q: 'DAL', sort: 'delay_asc', min: 10 })
    })
    const sp = new URLSearchParams(window.location.search)
    expect(sp.get('tab')).toBe('carriers')
    expect(sp.get('q')).toBe('DAL')
    expect(sp.get('sort')).toBe('delay_asc')
    expect(sp.get('min')).toBe('10')
  })

  it('elides defaults from URL (tab=airports, sort=on_time_desc, min=1)', () => {
    const { result } = renderHook(() => useFlightLookupParams())
    act(() => {
      result.current[1]({ tab: 'airports', sort: 'on_time_desc', min: 1 })
    })
    const sp = new URLSearchParams(window.location.search)
    expect(sp.get('tab')).toBeNull()
    expect(sp.get('sort')).toBeNull()
    expect(sp.get('min')).toBeNull()
  })

  it('elides empty q from URL', () => {
    const { result } = renderHook(() => useFlightLookupParams())
    act(() => {
      result.current[1]({ q: '' })
    })
    const sp = new URLSearchParams(window.location.search)
    expect(sp.get('q')).toBeNull()
  })

  it('elides null route from URL', () => {
    setSearch('route=KJFK-KLAX')
    const { result } = renderHook(() => useFlightLookupParams())
    act(() => {
      result.current[1]({ route: null })
    })
    const sp = new URLSearchParams(window.location.search)
    expect(sp.get('route')).toBeNull()
  })

  it('state reflects updated params after update call', () => {
    const { result } = renderHook(() => useFlightLookupParams())
    act(() => {
      result.current[1]({ q: 'KJFK', tab: 'carriers' })
    })
    const [params] = result.current
    expect(params.q).toBe('KJFK')
    expect(params.tab).toBe('carriers')
  })

  it('syncs state on popstate event', () => {
    const { result } = renderHook(() => useFlightLookupParams())
    act(() => {
      window.history.replaceState({}, '', '/?q=POP&tab=carriers')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    expect(result.current[0].q).toBe('POP')
    expect(result.current[0].tab).toBe('carriers')
  })

  it('removes popstate listener on unmount', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const { unmount } = renderHook(() => useFlightLookupParams())
    unmount()
    expect(removeSpy).toHaveBeenCalledWith('popstate', expect.any(Function))
    removeSpy.mockRestore()
  })

  it('returns correct FlightLookupParams type shape', () => {
    const { result } = renderHook(() => useFlightLookupParams())
    const [params] = result.current
    const _typed: FlightLookupParams = params
    expect(_typed).toBeDefined()
  })
})
