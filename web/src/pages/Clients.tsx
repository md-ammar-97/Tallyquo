import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'

interface Client {
  id: string
  legal_name: string
  country_code: string
  region_code: string | null
  tax_treatment: string
  outstanding_cad: string
  has_overdue: boolean
}

interface ClientSummaryPage {
  items: Client[]
  total: number
}

const emptyForm = {
  legal_name: '',
  country_code: 'CA',
  region_code: '',
  tax_treatment: 'taxable',
}

const PAGE_SIZE = 20

// Display-only: the client-level GST/HST registration status a tax
// treatment badge shows. Real tax computation always happens
// server-side per invoice (tax/engine.py) -- this never feeds a
// calculation, only labels what a client's default is. PST/QST are
// deliberately not shown here: they're an invoice-level opt-in
// (include_provincial_sales_tax), not a stored client default, so a
// compound "GST + PST" label would imply data this record doesn't have.
const HST_PROVINCES: Record<string, number> = { ON: 13, NS: 14, NB: 15, NL: 15, PE: 15 }
const GST_RATE = 5

function taxLabel(c: Client): string {
  if (c.tax_treatment === 'zero_rated_export') return 'Zero-rated export'
  if (c.tax_treatment === 'not_registered') return 'Not registered'
  if (c.tax_treatment === 'exempt') return 'Exempt'
  const rate = c.region_code ? HST_PROVINCES[c.region_code] : undefined
  if (rate) return `${c.region_code} — ${rate}% HST`
  return c.region_code ? `${c.region_code} — ${GST_RATE}% GST` : `${GST_RATE}% GST`
}

function formatMoney(amount: string): string {
  return `CAD ${Number(amount).toLocaleString('en-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export default function Clients() {
  const [clients, setClients] = useState<Client[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [form, setForm] = useState(emptyForm)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function load() {
    api
      .get<ClientSummaryPage>(`/clients/summary?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`)
      .then((data) => {
        setClients(data.items)
        setTotal(data.total)
      })
  }

  useEffect(load, [page])

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
      setPage(0)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create client.')
    } finally {
      setSaving(false)
    }
  }

  const from = total === 0 ? 0 : page * PAGE_SIZE + 1
  const to = Math.min(total, (page + 1) * PAGE_SIZE)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Clients</h1>
          <p className="caption" style={{ marginTop: -8, marginBottom: 16 }}>
            Manage your active clients, jurisdictions, and standard tax treatments.
          </p>
        </div>
        <button className="primary" onClick={() => setShowForm((s) => !s)}>
          {showForm ? 'Cancel' : '+ Add Client'}
        </button>
      </div>

      {showForm && (
        <div className="block">
          <div className="block-header">
            <h2>Add client</h2>
          </div>
          <div className="block-body">
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
        </div>
      )}

      <div className="block">
        <div className="block-header">
          <h2>All clients</h2>
          <button onClick={() => downloadFile('/clients/export.csv', 'clients.csv')}>Export CSV</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Legal name</th>
              <th>Jurisdiction</th>
              <th>Default tax treatment</th>
              <th>Outstanding</th>
              <th></th>
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
                  <span className={`badge ${c.tax_treatment}`}>{taxLabel(c)}</span>
                </td>
                <td className="amount" style={{ fontFamily: 'var(--font-mono)' }}>
                  <span style={c.has_overdue ? { color: 'var(--color-status-overdue)' } : undefined}>
                    {formatMoney(c.outstanding_cad)}
                  </span>
                </td>
                <td>
                  <Link className="link-button" to={`/clients/${c.id}`}>
                    View
                  </Link>
                </td>
              </tr>
            ))}
            {clients.length === 0 && (
              <tr>
                <td colSpan={5} className="caption" style={{ padding: 24 }}>
                  No clients yet. Add the people you bill -- we'll work out the right tax treatment for each one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {total > 0 && (
          <div
            className="block-body"
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 12 }}
          >
            <span className="caption">
              Showing {from}-{to} of {total} clients
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                ← Previous
              </button>
              <button disabled={to >= total} onClick={() => setPage((p) => p + 1)}>
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
