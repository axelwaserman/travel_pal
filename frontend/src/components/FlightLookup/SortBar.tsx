import { SORT_VALUES } from '../../hooks/useFlightLookupParams'
import type { FlightLookupParams } from '../../hooks/useFlightLookupParams'

type SortValue = FlightLookupParams['sort']

// Exhaustive map — TypeScript will error if a new sort value is added to
// SORT_VALUES without a corresponding label entry here.
const SORT_LABELS: Record<SortValue, string> = {
  on_time_desc: 'On-time ↓',
  on_time_asc: 'On-time ↑',
  delay_asc: 'Avg delay ↑',
  delay_desc: 'Avg delay ↓',
  volume_desc: 'Flights ↓',
  volume_asc: 'Flights ↑',
  volatility_asc: 'Volatility ↑',
}

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
      onChange={e => {
        const v = e.target.value
        if (!SORT_VALUES.includes(v as SortValue)) return
        onChange(v as SortValue)
      }}
    >
      {SORT_VALUES.map(v => (
        <option key={v} value={v}>
          {SORT_LABELS[v]}
        </option>
      ))}
    </select>
  )
}
