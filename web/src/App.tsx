import { useEffect, useState } from 'react'

// Phase 0 only proves the environment wiring works end to end (SPA -> API).
// The real design system (block primitives, tokens, badges) is Phase 1
// workstream 1.22 (implementation-plan.md) -- deliberately not built here.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type HealthState =
  | { status: 'checking' }
  | { status: 'ok' }
  | { status: 'error'; message: string }

function App() {
  const [health, setHealth] = useState<HealthState>({ status: 'checking' })

  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE_URL}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(() => {
        if (!cancelled) setHealth({ status: 'ok' })
      })
      .catch((err: Error) => {
        if (!cancelled) setHealth({ status: 'error', message: err.message })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem' }}>
      <h1>Tallyquo</h1>
      <p>Phase 0 environment check — API connectivity from the SPA.</p>
      <p>
        API ({API_BASE_URL}):{' '}
        {health.status === 'checking' && 'checking…'}
        {health.status === 'ok' && '✓ reachable'}
        {health.status === 'error' && `✗ ${health.message}`}
      </p>
    </main>
  )
}

export default App
