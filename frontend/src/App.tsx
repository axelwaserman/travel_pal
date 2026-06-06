import { Component, ReactNode } from 'react'
import FlightLookup from './components/FlightLookup/FlightLookup'
import TimelinessDashboard from './components/TimelinessDashboard/TimelinessDashboard'
import CancellationSection from './components/CancellationSection/CancellationSection'

interface ErrorBoundaryState {
  error: Error | null
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <main>
          <h1>TravelPal</h1>
          <p role="alert" style={{ color: 'red' }}>
            Failed to load: {this.state.error.message}
          </p>
        </main>
      )
    }
    return this.props.children
  }
}

const AIRPORT_ICAO = import.meta.env.VITE_AIRPORT_ICAO ?? 'KJFK'

export default function App() {
  return (
    <ErrorBoundary>
      <main>
        <header>
          <h1>TravelPal</h1>
          <p>Flight performance analytics for {AIRPORT_ICAO}</p>
        </header>
        <TimelinessDashboard airportIcao={AIRPORT_ICAO} />
        <FlightLookup airportIcao={AIRPORT_ICAO} />
        <CancellationSection airportIcao={AIRPORT_ICAO} />
      </main>
    </ErrorBoundary>
  )
}
