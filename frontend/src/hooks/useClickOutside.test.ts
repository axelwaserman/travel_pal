import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useRef } from 'react'
import { useClickOutside } from './useClickOutside'

describe('useClickOutside', () => {
  let container: HTMLDivElement
  let inner: HTMLSpanElement
  let outside: HTMLDivElement

  beforeEach(() => {
    container = document.createElement('div')
    inner = document.createElement('span')
    container.appendChild(inner)
    document.body.appendChild(container)

    outside = document.createElement('div')
    document.body.appendChild(outside)
  })

  afterEach(() => {
    document.body.removeChild(container)
    document.body.removeChild(outside)
    vi.restoreAllMocks()
  })

  it('calls callback when clicking outside the ref element', () => {
    const callback = vi.fn()
    renderHook(() => {
      const ref = useRef(container)
      useClickOutside(ref, callback)
    })
    const outsideEvent = new MouseEvent('mousedown', { bubbles: true })
    Object.defineProperty(outsideEvent, 'target', { value: outside })
    document.dispatchEvent(outsideEvent)
    expect(callback).toHaveBeenCalledOnce()
  })

  it('does not call callback when clicking inside the ref element', () => {
    const callback = vi.fn()
    renderHook(() => {
      const ref = useRef(container)
      useClickOutside(ref, callback)
    })
    // Dispatch a mousedown whose event.target is the inner child (inside the ref).
    // Object.defineProperty overrides the readonly target so ref.current.contains(e.target)
    // returns true, and the callback must NOT fire.
    const insideEvent = new MouseEvent('mousedown', { bubbles: true })
    Object.defineProperty(insideEvent, 'target', { value: inner })
    document.dispatchEvent(insideEvent)
    expect(callback).not.toHaveBeenCalled()
  })

  it('does not call callback when enabled=false', () => {
    const callback = vi.fn()
    renderHook(() => {
      const ref = useRef(container)
      useClickOutside(ref, callback, false)
    })
    const event = new MouseEvent('mousedown', { bubbles: true })
    Object.defineProperty(event, 'target', { value: outside })
    document.dispatchEvent(event)
    expect(callback).not.toHaveBeenCalled()
  })

  it('removes listener on unmount', () => {
    const removeSpy = vi.spyOn(document, 'removeEventListener')
    const callback = vi.fn()
    const { unmount } = renderHook(() => {
      const ref = useRef(container)
      useClickOutside(ref, callback)
    })
    unmount()
    expect(removeSpy).toHaveBeenCalledWith('mousedown', expect.any(Function))
  })

  it('re-registers listener when enabled changes from false to true', () => {
    const callback = vi.fn()
    const { rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => {
        const ref = useRef(container)
        useClickOutside(ref, callback, enabled)
      },
      { initialProps: { enabled: false } },
    )

    const outsideEvent = new MouseEvent('mousedown', { bubbles: true })
    Object.defineProperty(outsideEvent, 'target', { value: outside })
    document.dispatchEvent(outsideEvent)
    expect(callback).not.toHaveBeenCalled()

    rerender({ enabled: true })
    const outsideEvent2 = new MouseEvent('mousedown', { bubbles: true })
    Object.defineProperty(outsideEvent2, 'target', { value: outside })
    document.dispatchEvent(outsideEvent2)
    expect(callback).toHaveBeenCalledOnce()
  })

  it('does not add listener when enabled=false', () => {
    const addSpy = vi.spyOn(document, 'addEventListener')
    const callback = vi.fn()
    renderHook(() => {
      const ref = useRef(container)
      useClickOutside(ref, callback, false)
    })
    expect(addSpy).not.toHaveBeenCalledWith('mousedown', expect.any(Function))
    addSpy.mockRestore()
  })
})
