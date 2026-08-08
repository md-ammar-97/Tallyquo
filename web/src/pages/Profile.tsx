import { useEffect, useRef, useState } from 'react'
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

  async function loadTemplates() {
    const rows = await api.get<Template[]>('/templates')
    setTemplates(rows)
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
          <h2>Invoice template</h2>
        </div>
        <div className="block-body">
          <p className="caption" style={{ marginBottom: 12 }}>
            Choose which template new invoices use. Import a template package (.json) someone shared with you, or
            export one of yours to share or back up.
          </p>
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Name</th>
                <th>Accent</th>
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
                        background: t.theme.accent_color || '#0D99FF',
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
                </tr>
              ))}
            </tbody>
          </table>
          {templateError && <p className="error-text">{templateError}</p>}
          <div style={{ marginTop: 12 }}>
            <label>
              <input ref={importInputRef} type="file" accept="application/json" onChange={handleImportTemplate} />
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}
