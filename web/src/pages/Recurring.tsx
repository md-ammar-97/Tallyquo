import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'

interface Rule {
  id: string
  client_name: string | null
  cadence: string
  next_run_date: string
  auto_issue: boolean
  is_paused: boolean
  last_run_date: string | null
  occurrences_remaining: number | null
}

export default function Recurring() {
  const [rules, setRules] = useState<Rule[]>([])
  const [error, setError] = useState<string | null>(null)

  function load() {
    api.get<Rule[]>('/recurring').then(setRules)
  }

  useEffect(load, [])

  async function act(id: string, action: 'pause' | 'resume' | 'skip') {
    setError(null)
    try {
      await api.post(`/recurring/${id}/${action}`)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not ${action} rule.`)
    }
  }

  return (
    <div>
      <h1>Recurring invoices</h1>

      <div className="block">
        <div className="block-header">
          <h2>All rules</h2>
        </div>
        {error && (
          <p className="error-text" style={{ padding: '0 16px' }}>
            {error}
          </p>
        )}
        <table>
          <thead>
            <tr>
              <th>Client</th>
              <th>Cadence</th>
              <th>Next run</th>
              <th>Auto-issue</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.id}>
                <td>{rule.client_name ?? '—'}</td>
                <td>{rule.cadence}</td>
                <td>{rule.next_run_date}</td>
                <td>{rule.auto_issue ? 'Yes' : 'No, drafts only'}</td>
                <td>
                  <span className={`badge ${rule.is_paused ? 'draft' : 'issued'}`}>
                    {rule.is_paused ? 'paused' : 'active'}
                  </span>
                </td>
                <td style={{ display: 'flex', gap: 8 }}>
                  {rule.is_paused ? (
                    <button onClick={() => act(rule.id, 'resume')}>Resume</button>
                  ) : (
                    <>
                      <button onClick={() => act(rule.id, 'skip')}>Skip next</button>
                      <button onClick={() => act(rule.id, 'pause')}>Pause</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {rules.length === 0 && (
              <tr>
                <td colSpan={6} className="caption" style={{ padding: 24 }}>
                  No recurring rules yet. Open an invoice and choose "Make recurring" to set one up.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
