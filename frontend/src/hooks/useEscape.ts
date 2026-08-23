import { useEffect, useRef } from 'react'

export function useEscape(callback: () => void, enabled = true) {
  const cbRef = useRef(callback)
  useEffect(() => { cbRef.current = callback })
  useEffect(() => {
    if (!enabled) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') cbRef.current() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [enabled])
}
