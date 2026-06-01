import { Component, ReactNode } from 'react'

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

export default function App() {
  return (
    <ErrorBoundary>
      <main>
        <h1>TravelPal</h1>
        <p>Loading...</p>
      </main>
    </ErrorBoundary>
  )
}
