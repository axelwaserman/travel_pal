import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

vi.mock('./db/queries', () => ({
  queryFlightLookup: vi.fn().mockResolvedValue([]),
  queryDailyTimeliness: vi.fn().mockResolvedValue([]),
  queryCarrierCancellations: vi.fn().mockResolvedValue([]),
  queryRouteCancellations: vi.fn().mockResolvedValue([]),
}))
vi.mock('./db/client', () => ({
  getDb: vi.fn(),
}))

import App from './App'

describe('App', () => {
  it('renders TravelPal heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: 'TravelPal' })).toBeInTheDocument()
  })
})
