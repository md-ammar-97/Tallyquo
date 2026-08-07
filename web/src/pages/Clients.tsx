import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'

interface Client {
  id: string
  legal_name: string
  country_code: string
  region_code: string | null
  tax_treatment: string
}

const emptyForm = {
  legal_name: '',
  country_code: 'CA',
  region_code: '',
  tax_treatment: 'taxable',
}

export default function Clients() {
  const [clients, setClients] = useState<Client[]>([])
  const [form, setForm] = useState(emptyForm)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function load() {
    api.get<Client[]>('/clients').then(setClients)
  }

  useEffect(load, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const body: Record<string, unknown> = { ...form }
      if (form.country_code !== 'CA') {
        body.tax_treatment = 'zero_rated_export'
        delete body.region_code
      }
      await api.post('/clients', body)
      setForm(emptyForm)
      setShowForm(false)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create client.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <h1>Clients</h1>

      <div className="block">
        <div className="block-header">
          <h2>All clients</h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => downloadFile('/clients/export.csv', 'clients.csv')}>Export CSV</button>
            <button className="primary" onClick={() => setShowForm((s) => !s)}>
              {showForm ? 'Cancel' : 'Add client'}
            </button>
          </div>
        </div>
        {showForm && (
          <div className="block-body" style={{ borderBottom: '1px solid var(--color-border-default)' }}>
            <form onSubmit={handleCreate}>
              <div className="field">
                <label>Legal name</label>
                <input
                  required
                  value={form.legal_name}
                  onChange={(e) => setForm({ ...form, legal_name: e.target.value })}
                />
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Country</label>
                  <select
                    value={form.country_code}
                    onChange={(e) => setForm({ ...form, country_code: e.target.value })}
                  >
                    <option value="CA">Canada</option>
                    <option value="US">United States</option>
                  </select>
                </div>
                {form.country_code === 'CA' && (
                  <div className="field">
                    <label>Province</label>
                    <input
                      required
                      placeholder="ON"
                      value={form.region_code}
                      onChange={(e) => setForm({ ...form, region_code: e.target.value.toUpperCase() })}
                    />
                  </div>
                )}
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                {form.country_code === 'CA'
                  ? 'Tax rate is derived from this province, not your own location.'
                  : 'Non-resident clients are zero-rated exports by default -- 0% tax, but still counts toward your $30,000 registration threshold.'}
              </p>
              {error && <p className="error-text">{error}</p>}
              <button type="submit" className="primary" disabled={saving}>
                {saving ? 'Saving…' : 'Add client'}
              </button>
            </form>
          </div>
        )}
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Location</th>
              <th>Tax treatment</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link to={`/clients/${c.id}`}>{c.legal_name}</Link>
                </td>
                <td>
                  {c.region_code ? `${c.region_code}, ` : ''}
                  {c.country_code}
                </td>
                <td>
                  <span className={`badge ${c.tax_treatment}`}>{c.tax_treatment.replace(/_/g, ' ')}</span>
                </td>
              </tr>
            ))}
            {clients.length === 0 && (
              <tr>
                <td colSpan={3} className="caption" style={{ padding: 24 }}>
                  No clients yet. Add the people you bill -- we'll work out the right tax treatment for each one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
