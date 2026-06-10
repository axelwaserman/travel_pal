import { type RefObject, useEffect, useRef } from 'react'

export function useClickOutside<T extends HTMLElement>(
  ref: RefObject<T>,
  callback: () => void,
  enabled = true,
) {
  const cbRef = useRef(callback)
  useEffect(() => { cbRef.current = callback })
  useEffect(() => {
    if (!enabled) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) cbRef.current()
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [ref, enabled])
}
