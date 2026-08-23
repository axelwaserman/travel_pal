import { useRef } from 'react'

type TabValue = 'airports' | 'carriers'

interface Props {
  value: TabValue
  onChange: (v: TabValue) => void
}

const TABS: { value: TabValue; label: string }[] = [
  { value: 'airports', label: 'Airports' },
  { value: 'carriers', label: 'Carriers' },
]

export default function SearchTabs({ value, onChange }: Props) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])

  function handleKeyDown(e: React.KeyboardEvent, index: number) {
    if (e.key === 'ArrowRight') {
      const next = (index + 1) % TABS.length
      tabRefs.current[next]?.focus()
    } else if (e.key === 'ArrowLeft') {
      const prev = (index - 1 + TABS.length) % TABS.length
      tabRefs.current[prev]?.focus()
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onChange(TABS[index].value)
    }
  }

  return (
    <div role="tablist" className="search-tabs" aria-label="Search mode">
      {TABS.map((tab, i) => (
        <button
          key={tab.value}
          role="tab"
          ref={el => { tabRefs.current[i] = el }}
          aria-selected={value === tab.value}
          tabIndex={value === tab.value ? 0 : -1}
          className={`search-tab${value === tab.value ? ' search-tab--active' : ''}`}
          onClick={() => {
            if (value !== tab.value) onChange(tab.value)
          }}
          onKeyDown={e => handleKeyDown(e, i)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
