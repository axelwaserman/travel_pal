import './ChartSpinner.css'

interface Props {
  label?: string
}

export function ChartSpinner({ label = 'Loading chart…' }: Props) {
  return (
    <div className="chart-spinner" role="status">
      <span className="chart-spinner__ring" aria-hidden="true" />
      <span className="chart-spinner__text">{label}</span>
    </div>
  )
}
