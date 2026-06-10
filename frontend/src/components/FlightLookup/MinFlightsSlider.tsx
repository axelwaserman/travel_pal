import { useEffect, useRef, useState } from 'react'

const MIN = 1
const MAX = 1000
const DEFAULT_DEBOUNCE_MS = 300

interface Props {
  value: number
  onChange: (v: number) => void
  debounceMs?: number
}

export default function MinFlightsSlider({
  value,
  onChange,
  debounceMs = DEFAULT_DEBOUNCE_MS,
}: Props) {
  const [localValue, setLocalValue] = useState(value)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Keep local value in sync when parent value changes externally.
  // Also clear any pending debounce to prevent the stale timer from
  // clobbering the parent's reset with the pre-reset value.
  useEffect(() => {
    setLocalValue(value)
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [value])

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const next = parseInt(e.target.value, 10)
    setLocalValue(next)

    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
    }
    timerRef.current = setTimeout(() => {
      onChange(next)
      timerRef.current = null
    }, debounceMs)
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
      }
    }
  }, [])

  return (
    <div className="min-flights-slider">
      <input
        type="range"
        min={MIN}
        max={MAX}
        value={localValue}
        aria-label="Minimum flights threshold"
        aria-valuemin={MIN}
        aria-valuemax={MAX}
        aria-valuenow={localValue}
        className="min-flights-slider__input"
        onChange={handleChange}
      />
      <span className="min-flights-slider__value">
        {`≥ ${localValue} flights`}
      </span>
    </div>
  )
}
