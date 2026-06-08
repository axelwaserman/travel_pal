import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ChartSpinner } from './ChartSpinner'

describe('ChartSpinner', () => {
  it('has role="status" for accessibility', () => {
    render(<ChartSpinner />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows the default label text when no label prop given', () => {
    render(<ChartSpinner />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading chart…')
  })

  it('shows custom label text when label prop is provided', () => {
    render(<ChartSpinner label="Loading carrier chart…" />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading carrier chart…')
  })

  it('renders visible label text', () => {
    render(<ChartSpinner label="Loading route chart…" />)
    expect(screen.getByText('Loading route chart…')).toBeInTheDocument()
  })

  it('marks the ring as aria-hidden so screen readers skip it', () => {
    render(<ChartSpinner />)
    const ring = document.querySelector('.chart-spinner__ring')
    expect(ring).toHaveAttribute('aria-hidden', 'true')
  })
})
