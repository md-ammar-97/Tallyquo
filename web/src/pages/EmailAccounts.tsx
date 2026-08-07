import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'

interface EmailAccount {
  id: string
  label: string
  from_name: string
  from_address: string
  smtp_host: string
  smtp_port: number
  smtp_security: string
  smtp_username: string
  is_default: boolean
  verified_at: string | null
}

const emptyForm = {
  label: '',
  from_name: '',
  from_address: '',
  smtp_host: '',
  smtp_port: '587',
  smtp_security: 'starttls',
  smtp_username: '',
  password: '',
  is_default: false,
}

export default function EmailAccounts() {
  const [accounts, setAccounts] = useState<EmailAccount[]>([])
  const [form, setForm] = useState(emptyForm)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [verifying, setVerifying] = useState<string | null>(null)
  const [verifyMessage, setVerifyMessage] = useState<Record<string, string>>({})

  function load() {
    api.get<EmailAccount[]>('/email-accounts').then(setAccounts)
  }

  useEffect(load, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.post('/email-accounts', { ...form, smtp_port: Number(form.smtp_port) })
      setForm(emptyForm)
      setShowForm(false)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save this account.')
    } finally {
      setSaving(false)
    }
  }

  async function handleVerify(id: string) {
    setVerifying(id)
    setVerifyMessage((m) => ({ ...m, [id]: '' }))
    try {
      await api.post(`/email-accounts/${id}/verify`)
      setVerifyMessage((m) => ({ ...m, [id]: 'Verified.' }))
      load()
    } catch (err) {
      setVerifyMessage((m) => ({ ...m, [id]: err instanceof ApiError ? err.message : 'Could not verify.' }))
    } finally {
      setVerifying(null)
    }
  }

  async function handleArchive(id: string) {
    if (!window.confirm('Remove this email account?')) return
    await api.delete(`/email-accounts/${id}`)
    load()
  }

  return (
    <div>
      <h1>Email accounts</h1>
      <p className="caption" style={{ marginBottom: 16 }}>
        Invoices are emailed through your own mail server, never a shared sender identity — add the account you
        want to send from below.
      </p>

      <div className="block">
        <div className="block-header">
          <h2>Configured accounts</h2>
          <button className="primary" onClick={() => setShowForm((s) => !s)}>
            {showForm ? 'Cancel' : 'Add account'}
          </button>
        </div>
        {showForm && (
          <div className="block-body" style={{ borderBottom: '1px solid var(--color-border-default)' }}>
            <form onSubmit={handleCreate}>
              <div className="field-row">
                <div className="field">
                  <label>Label</label>
                  <input
                    required
                    placeholder="My Gmail"
                    value={form.label}
                    onChange={(e) => setForm({ ...form, label: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>From name</label>
                  <input
                    required
                    value={form.from_name}
                    onChange={(e) => setForm({ ...form, from_name: e.target.value })}
                  />
                </div>
              </div>
              <div className="field">
                <label>From address</label>
                <input
                  required
                  type="email"
                  value={form.from_address}
                  onChange={(e) => setForm({ ...form, from_address: e.target.value })}
                />
              </div>
              <div className="field-row">
                <div className="field">
                  <label>SMTP host</label>
                  <input
                    required
                    placeholder="smtp.gmail.com"
                    value={form.smtp_host}
                    onChange={(e) => setForm({ ...form, smtp_host: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>Port</label>
                  <input
                    required
                    value={form.smtp_port}
                    onChange={(e) => setForm({ ...form, smtp_port: e.target.value })}
                  />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Security</label>
                  <select
                    value={form.smtp_security}
                    onChange={(e) => setForm({ ...form, smtp_security: e.target.value })}
                  >
                    <option value="starttls">STARTTLS</option>
                    <option value="tls">TLS</option>
                    <option value="none">None</option>
                  </select>
                </div>
                <div className="field">
                  <label>Username</label>
                  <input
                    required
                    value={form.smtp_username}
                    onChange={(e) => setForm({ ...form, smtp_username: e.target.value })}
                  />
                </div>
              </div>
              <div className="field">
                <label>Password (or app password)</label>
                <input
                  required
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                />
              </div>
              <div className="field">
                <label>
                  <input
                    type="checkbox"
                    style={{ width: 'auto', marginRight: 8 }}
                    checked={form.is_default}
                    onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                  />
                  Use as default sending account
                </label>
              </div>
              {error && <p className="error-text">{error}</p>}
              <button type="submit" className="primary" disabled={saving}>
                {saving ? 'Saving…' : 'Add account'}
              </button>
            </form>
          </div>
        )}
        <table>
          <thead>
            <tr>
              <th>Label</th>
              <th>From</th>
              <th>Server</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id}>
                <td>
                  {a.label} {a.is_default && <span className="badge taxable">default</span>}
                </td>
                <td>
                  {a.from_name} &lt;{a.from_address}&gt;
                </td>
                <td>
                  {a.smtp_host}:{a.smtp_port} ({a.smtp_security})
                </td>
                <td>
                  {a.verified_at ? (
                    <span className="badge paid">verified</span>
                  ) : (
                    <span className="badge draft">unverified</span>
                  )}
                  {verifyMessage[a.id] && <div className="caption">{verifyMessage[a.id]}</div>}
                </td>
                <td style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => handleVerify(a.id)} disabled={verifying === a.id}>
                    {verifying === a.id ? 'Testing…' : 'Test'}
                  </button>
                  <button className="danger" onClick={() => handleArchive(a.id)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {accounts.length === 0 && (
              <tr>
                <td colSpan={5} className="caption" style={{ padding: 24 }}>
                  No email accounts yet. Add one to send invoices from your own address.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
