import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useEscape } from './useEscape'

describe('useEscape', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('calls callback when Escape key is pressed', () => {
    const callback = vi.fn()
    renderHook(() => useEscape(callback))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(callback).toHaveBeenCalledOnce()
  })

  it('does not call callback for non-Escape keys', () => {
    const callback = vi.fn()
    renderHook(() => useEscape(callback))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab' }))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }))
    expect(callback).not.toHaveBeenCalled()
  })

  it('does not call callback when enabled=false', () => {
    const callback = vi.fn()
    renderHook(() => useEscape(callback, false))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(callback).not.toHaveBeenCalled()
  })

  it('removes listener on unmount', () => {
    const removeSpy = vi.spyOn(document, 'removeEventListener')
    const callback = vi.fn()
    const { unmount } = renderHook(() => useEscape(callback))
    unmount()
    expect(removeSpy).toHaveBeenCalledWith('keydown', expect.any(Function))
  })

  it('re-registers listener when enabled changes from false to true', () => {
    const callback = vi.fn()
    const { rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => useEscape(callback, enabled),
      { initialProps: { enabled: false } },
    )
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(callback).not.toHaveBeenCalled()

    rerender({ enabled: true })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(callback).toHaveBeenCalledOnce()
  })

  it('does not add listener when enabled=false (default is true)', () => {
    const addSpy = vi.spyOn(document, 'addEventListener')
    const callback = vi.fn()
    renderHook(() => useEscape(callback, false))
    expect(addSpy).not.toHaveBeenCalledWith('keydown', expect.any(Function))
    addSpy.mockRestore()
  })
})
