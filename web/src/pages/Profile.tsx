import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'

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
      }
    })
  }, [])

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
    </div>
  )
}
