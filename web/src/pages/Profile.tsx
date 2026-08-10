import { Fragment, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'

interface BusinessProfile {
  legal_name: string
  address_line1: string
  city: string
  region_code: string
  postal_code: string
  country_code: string
  registration_status: string
  gst_hst_number: string | null
  registration_effective_date: string | null
  default_template_id: string | null
}

interface Template {
  id: string
  name: string
  theme: { accent_color?: string }
  is_system: boolean
  is_default: boolean
}

interface PaymentInstruction {
  id: string
  label: string
  method: string
  provider: string | null
  account_holder: string | null
  currency: string
  is_default: boolean
  fields_masked: Record<string, string>
}

const PAYMENT_METHODS = ['etransfer', 'eft', 'ach', 'wire', 'cheque', 'cash', 'card', 'other']

const emptyPaymentForm = {
  label: '',
  method: 'etransfer',
  provider: '',
  account_holder: '',
  currency: 'CAD',
  is_default: false,
}

const emptyProfile = {
  legal_name: '',
  address_line1: '',
  city: '',
  region_code: '',
  postal_code: '',
  country_code: 'CA',
}

export default function Profile() {
  const [profile, setProfile] = useState<BusinessProfile | null>(null)
  const [form, setForm] = useState(emptyProfile)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const [regStatus, setRegStatus] = useState('not_registered')
  const [gstNumber, setGstNumber] = useState('')
  const [regDate, setRegDate] = useState('')
  const [regSaving, setRegSaving] = useState(false)
  const [regError, setRegError] = useState<string | null>(null)

  const [templates, setTemplates] = useState<Template[]>([])
  const [defaultTemplateId, setDefaultTemplateId] = useState<string | null>(null)
  const [templateSaving, setTemplateSaving] = useState<string | null>(null)
  const [templateError, setTemplateError] = useState<string | null>(null)
  const importInputRef = useRef<HTMLInputElement>(null)

  const [payInstructions, setPayInstructions] = useState<PaymentInstruction[]>([])
  const [payForm, setPayForm] = useState(emptyPaymentForm)
  const [payFields, setPayFields] = useState<{ key: string; value: string }[]>([{ key: '', value: '' }])
  const [paySaving, setPaySaving] = useState(false)
  const [payError, setPayError] = useState<string | null>(null)
  const [revealed, setRevealed] = useState<Record<string, Record<string, string>>>({})

  async function loadTemplates() {
    const rows = await api.get<Template[]>('/templates')
    setTemplates(rows)
  }

  async function loadPaymentInstructions() {
    const rows = await api.get<PaymentInstruction[]>('/payment-instructions')
    setPayInstructions(rows)
  }

  useEffect(() => {
    api.get<BusinessProfile | null>('/profile').then((p) => {
      if (p) {
        setProfile(p)
        setForm({
          legal_name: p.legal_name,
          address_line1: p.address_line1,
          city: p.city,
          region_code: p.region_code,
          postal_code: p.postal_code,
          country_code: p.country_code,
        })
        setRegStatus(p.registration_status)
        setGstNumber(p.gst_hst_number ?? '')
        setRegDate(p.registration_effective_date ?? '')
        setDefaultTemplateId(p.default_template_id)
      }
    })
    loadTemplates()
    loadPaymentInstructions()
  }, [])

  async function handleSetDefaultTemplate(templateId: string) {
    setTemplateSaving(templateId)
    setTemplateError(null)
    try {
      await api.put('/templates/default', { template_id: templateId })
      setDefaultTemplateId(templateId)
    } catch (err) {
      setTemplateError(err instanceof ApiError ? err.message : 'Could not set default template.')
    } finally {
      setTemplateSaving(null)
    }
  }

  async function handleImportTemplate(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setTemplateError(null)
    try {
      const text = await file.text()
      const pkg = JSON.parse(text)
      await api.post('/templates/import', pkg)
      await loadTemplates()
    } catch (err) {
      setTemplateError(err instanceof ApiError ? err.message : 'Could not import that file -- check it\'s a valid template package.')
    } finally {
      if (importInputRef.current) importInputRef.current.value = ''
    }
  }

  async function handleAddPaymentInstruction(e: React.FormEvent) {
    e.preventDefault()
    setPaySaving(true)
    setPayError(null)
    try {
      const fields: Record<string, string> = {}
      for (const { key, value } of payFields) {
        if (key.trim()) fields[key.trim()] = value
      }
      await api.post('/payment-instructions', {
        ...payForm,
        provider: payForm.provider || null,
        account_holder: payForm.account_holder || null,
        fields,
      })
      setPayForm(emptyPaymentForm)
      setPayFields([{ key: '', value: '' }])
      await loadPaymentInstructions()
    } catch (err) {
      setPayError(err instanceof ApiError ? err.message : 'Could not save payment instruction.')
    } finally {
      setPaySaving(false)
    }
  }

  async function handleReveal(id: string) {
    if (revealed[id]) {
      setRevealed((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      return
    }
    try {
      const data = await api.get<{ fields: Record<string, string> }>(`/payment-instructions/${id}/reveal`)
      setRevealed((prev) => ({ ...prev, [id]: data.fields }))
    } catch (err) {
      setPayError(err instanceof ApiError ? err.message : 'Could not reveal payment instruction.')
    }
  }

  async function handleArchivePaymentInstruction(id: string) {
    try {
      await api.delete(`/payment-instructions/${id}`)
      await loadPaymentInstructions()
    } catch (err) {
      setPayError(err instanceof ApiError ? err.message : 'Could not remove payment instruction.')
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      const updated = await api.patch<BusinessProfile>('/profile', form)
      setProfile(updated)
      setMessage('Saved.')
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : 'Could not save.')
    } finally {
      setSaving(false)
    }
  }

  async function handleRegistrationSave(e: React.FormEvent) {
    e.preventDefault()
    setRegSaving(true)
    setRegError(null)
    try {
      const body: Record<string, unknown> = { registration_status: regStatus }
      if (regStatus === 'registered') {
        body.gst_hst_number = gstNumber
        body.registration_effective_date = regDate
      }
      const updated = await api.patch<BusinessProfile>('/profile/registration', body)
      setProfile(updated)
    } catch (err) {
      setRegError(err instanceof ApiError ? err.message : 'Could not save.')
    } finally {
      setRegSaving(false)
    }
  }

  return (
    <div>
      <h1>Business profile</h1>

      <div className="block">
        <div className="block-header">
          <h2>Identity &amp; address</h2>
        </div>
        <div className="block-body">
          <form onSubmit={handleSave}>
            <div className="field">
              <label>Legal name</label>
              <input
                required
                value={form.legal_name}
                onChange={(e) => setForm({ ...form, legal_name: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Address</label>
              <input
                required
                value={form.address_line1}
                onChange={(e) => setForm({ ...form, address_line1: e.target.value })}
              />
            </div>
            <div className="field-row">
              <div className="field">
                <label>City</label>
                <input required value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
              </div>
              <div className="field">
                <label>Province</label>
                <input
                  required
                  placeholder="ON"
                  value={form.region_code}
                  onChange={(e) => setForm({ ...form, region_code: e.target.value.toUpperCase() })}
                />
              </div>
            </div>
            <div className="field">
              <label>Postal code</label>
              <input
                required
                value={form.postal_code}
                onChange={(e) => setForm({ ...form, postal_code: e.target.value })}
              />
            </div>
            {message && <p className="caption">{message}</p>}
            <button type="submit" className="primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </form>
        </div>
      </div>

      {profile && (
        <div className="block">
          <div className="block-header">
            <h2>GST/HST registration</h2>
          </div>
          <div className="block-body">
            <form onSubmit={handleRegistrationSave}>
              <div className="field">
                <label>Status</label>
                <select value={regStatus} onChange={(e) => setRegStatus(e.target.value)}>
                  <option value="not_registered">Not registered</option>
                  <option value="registration_pending">Registration pending</option>
                  <option value="registered">Registered</option>
                </select>
              </div>
              {regStatus === 'registered' && (
                <>
                  <div className="field">
                    <label>GST/HST number</label>
                    <input
                      required
                      placeholder="123456789RT0001"
                      value={gstNumber}
                      onChange={(e) => setGstNumber(e.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label>Effective date</label>
                    <input
                      required
                      type="date"
                      value={regDate}
                      onChange={(e) => setRegDate(e.target.value)}
                    />
                  </div>
                </>
              )}
              {regError && <p className="error-text">{regError}</p>}
              <button type="submit" className="primary" disabled={regSaving}>
                {regSaving ? 'Saving…' : 'Save'}
              </button>
            </form>
          </div>
        </div>
      )}

      <div className="block">
        <div className="block-header">
          <h2>Payment instructions</h2>
        </div>
        <div className="block-body">
          <p className="caption" style={{ marginBottom: 12 }}>
            Shown on issued invoices so clients know how to pay you. The default account is frozen onto each invoice
            at the moment it's issued -- changing it here never alters an invoice already sent.
          </p>
          {payInstructions.length > 0 && (
            <table style={{ marginBottom: 16 }}>
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Method</th>
                  <th>Currency</th>
                  <th></th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {payInstructions.map((p) => (
                  <Fragment key={p.id}>
                    <tr>
                      <td>
                        {p.label} {p.is_default && <span className="badge paid">default</span>}
                      </td>
                      <td>{p.method}</td>
                      <td>{p.currency}</td>
                      <td>
                        <button type="button" className="link-button" onClick={() => handleReveal(p.id)}>
                          {revealed[p.id] ? 'Hide' : 'Reveal'}
                        </button>
                      </td>
                      <td>
                        <button type="button" className="link-button" onClick={() => handleArchivePaymentInstruction(p.id)}>
                          Remove
                        </button>
                      </td>
                    </tr>
                    {revealed[p.id] && (
                      <tr>
                        <td colSpan={5}>
                          <p className="caption">
                            {Object.entries(revealed[p.id])
                              .map(([k, v]) => `${k}: ${v}`)
                              .join(' · ') || '(no additional fields)'}
                          </p>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
          <form onSubmit={handleAddPaymentInstruction}>
            <div className="field-row">
              <div className="field">
                <label>Label</label>
                <input
                  required
                  placeholder="Main account"
                  value={payForm.label}
                  onChange={(e) => setPayForm({ ...payForm, label: e.target.value })}
                />
              </div>
              <div className="field">
                <label>Method</label>
                <select value={payForm.method} onChange={(e) => setPayForm({ ...payForm, method: e.target.value })}>
                  {PAYMENT_METHODS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="field-row">
              <div className="field">
                <label>Provider (optional)</label>
                <input
                  placeholder="e.g. RBC, Interac"
                  value={payForm.provider}
                  onChange={(e) => setPayForm({ ...payForm, provider: e.target.value })}
                />
              </div>
              <div className="field">
                <label>Currency</label>
                <input
                  required
                  value={payForm.currency}
                  onChange={(e) => setPayForm({ ...payForm, currency: e.target.value.toUpperCase() })}
                />
              </div>
            </div>
            <div className="field">
              <label>Account holder (optional)</label>
              <input
                value={payForm.account_holder}
                onChange={(e) => setPayForm({ ...payForm, account_holder: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Details (e.g. e-transfer email, account number)</label>
              {payFields.map((f, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                  <input
                    placeholder="Field name"
                    value={f.key}
                    onChange={(e) => {
                      const next = [...payFields]
                      next[i] = { ...next[i], key: e.target.value }
                      setPayFields(next)
                    }}
                  />
                  <input
                    placeholder="Value"
                    value={f.value}
                    onChange={(e) => {
                      const next = [...payFields]
                      next[i] = { ...next[i], value: e.target.value }
                      setPayFields(next)
                    }}
                  />
                  <button type="button" className="link-button" onClick={() => setPayFields(payFields.filter((_, j) => j !== i))}>
                    &times;
                  </button>
                </div>
              ))}
              <button type="button" className="link-button" onClick={() => setPayFields([...payFields, { key: '', value: '' }])}>
                + Add field
              </button>
            </div>
            <div className="field">
              <label>
                <input
                  type="checkbox"
                  style={{ width: 'auto', marginRight: 8 }}
                  checked={payForm.is_default}
                  onChange={(e) => setPayForm({ ...payForm, is_default: e.target.checked })}
                />{' '}
                Set as default (used on new invoices)
              </label>
            </div>
            {payError && <p className="error-text">{payError}</p>}
            <button type="submit" className="primary" disabled={paySaving}>
              {paySaving ? 'Saving…' : 'Add payment instruction'}
            </button>
          </form>
        </div>
      </div>

      <div className="block">
        <div className="block-header">
          <h2>Invoice template</h2>
        </div>
        <div className="block-body">
          <p className="caption" style={{ marginBottom: 12 }}>
            Choose which template new invoices use, or build your own: reorder the payment/notes sections, pick a
            font size, upload a logo. Import a template package (.json) someone shared with you, or export one of
            yours to share or back up.
          </p>
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Name</th>
                <th>Accent</th>
                <th></th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {templates.map((t) => (
                <tr key={t.id}>
                  <td>
                    <input
                      type="radio"
                      name="default_template"
                      checked={defaultTemplateId === t.id}
                      disabled={templateSaving !== null}
                      onChange={() => handleSetDefaultTemplate(t.id)}
                    />
                  </td>
                  <td>
                    {t.name} {t.is_system && <span className="caption">(system)</span>}
                  </td>
                  <td>
                    <span
                      style={{
                        display: 'inline-block',
                        width: 14,
                        height: 14,
                        borderRadius: 3,
                        background: t.theme.accent_color || '#1A365D',
                        verticalAlign: 'middle',
                      }}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => downloadFile(`/templates/${t.id}/export`, `${t.name}.tallyquo-template.json`)}
                    >
                      Export
                    </button>
                  </td>
                  <td>
                    {t.is_system ? (
                      <Link className="link-button" to={`/settings/templates/new?clone=${t.id}`}>
                        Customize
                      </Link>
                    ) : (
                      <Link className="link-button" to={`/settings/templates/${t.id}/edit`}>
                        Edit
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {templateError && <p className="error-text">{templateError}</p>}
          <div style={{ marginTop: 12, display: 'flex', gap: 16, alignItems: 'center' }}>
            <Link className="link-button" to="/settings/templates/new">
              + New custom template
            </Link>
            <label>
              <input ref={importInputRef} type="file" accept="application/json" onChange={handleImportTemplate} />
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}
