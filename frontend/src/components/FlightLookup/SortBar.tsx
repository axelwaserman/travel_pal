import type { FlightLookupParams } from '../../hooks/useFlightLookupParams'

type SortValue = FlightLookupParams['sort']

interface SortOption {
  value: SortValue
  label: string
}

const SORT_OPTIONS: SortOption[] = [
  { value: 'on_time_desc', label: 'On-time ↓' },
  { value: 'on_time_asc', label: 'On-time ↑' },
  { value: 'delay_asc', label: 'Avg delay ↑' },
  { value: 'delay_desc', label: 'Avg delay ↓' },
  { value: 'volume_desc', label: 'Flights ↓' },
  { value: 'volume_asc', label: 'Flights ↑' },
  { value: 'volatility_asc', label: 'Volatility ↑' },
]

interface Props {
  value: SortValue
  onChange: (v: SortValue) => void
}

export default function SortBar({ value, onChange }: Props) {
  return (
    <select
      className="sort-bar"
      value={value}
      aria-label="Sort results"
      onChange={e => onChange(e.target.value as SortValue)}
    >
      {SORT_OPTIONS.map(opt => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}
