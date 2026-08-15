import { Fragment, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const selectClass = 'h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm'
const fieldRow = 'flex flex-wrap gap-4'
const fieldCol = 'flex flex-1 flex-col gap-1.5'

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
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">Business profile</h1>

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Identity &amp; address</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSave} className="flex flex-col gap-4">
            <div className={fieldCol}>
              <Label>Legal name</Label>
              <Input required value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} />
            </div>
            <div className={fieldCol}>
              <Label>Address</Label>
              <Input required value={form.address_line1} onChange={(e) => setForm({ ...form, address_line1: e.target.value })} />
            </div>
            <div className={fieldRow}>
              <div className={fieldCol}>
                <Label>City</Label>
                <Input required value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
              </div>
              <div className={fieldCol}>
                <Label>Province</Label>
                <Input
                  required
                  placeholder="ON"
                  value={form.region_code}
                  onChange={(e) => setForm({ ...form, region_code: e.target.value.toUpperCase() })}
                />
              </div>
            </div>
            <div className={fieldCol}>
              <Label>Postal code</Label>
              <Input required value={form.postal_code} onChange={(e) => setForm({ ...form, postal_code: e.target.value })} />
            </div>
            {message && <p className="text-body-sm text-mute">{message}</p>}
            <Button type="submit" disabled={saving} className="self-start">
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {profile && (
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-display-xs font-semibold text-ink">GST/HST registration</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleRegistrationSave} className="flex flex-col gap-4">
              <div className={fieldCol}>
                <Label>Status</Label>
                <select className={selectClass} value={regStatus} onChange={(e) => setRegStatus(e.target.value)}>
                  <option value="not_registered">Not registered</option>
                  <option value="registration_pending">Registration pending</option>
                  <option value="registered">Registered</option>
                </select>
              </div>
              {regStatus === 'registered' && (
                <>
                  <div className={fieldCol}>
                    <Label>GST/HST number</Label>
                    <Input required placeholder="123456789RT0001" value={gstNumber} onChange={(e) => setGstNumber(e.target.value)} />
                  </div>
                  <div className={fieldCol}>
                    <Label>Effective date</Label>
                    <Input required type="date" value={regDate} onChange={(e) => setRegDate(e.target.value)} />
                  </div>
                </>
              )}
              {regError && <p className="text-body-sm text-negative">{regError}</p>}
              <Button type="submit" disabled={regSaving} className="self-start">
                {regSaving ? 'Saving…' : 'Save'}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Payment instructions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-body-sm text-mute">
            Shown on issued invoices so clients know how to pay you. The default account is frozen onto each invoice
            at the moment it's issued -- changing it here never alters an invoice already sent.
          </p>
          {payInstructions.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Label</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Currency</TableHead>
                  <TableHead></TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {payInstructions.map((p) => (
                  <Fragment key={p.id}>
                    <TableRow>
                      <TableCell className="flex items-center gap-2">
                        {p.label} {p.is_default && <Badge variant="secondary" className="bg-positive/15 text-positive-deep">default</Badge>}
                      </TableCell>
                      <TableCell>{p.method}</TableCell>
                      <TableCell>{p.currency}</TableCell>
                      <TableCell>
                        <button
                          type="button"
                          className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
                          onClick={() => handleReveal(p.id)}
                        >
                          {revealed[p.id] ? 'Hide' : 'Reveal'}
                        </button>
                      </TableCell>
                      <TableCell>
                        <button
                          type="button"
                          className="text-body-sm font-medium text-negative underline underline-offset-2 hover:text-negative-deep"
                          onClick={() => handleArchivePaymentInstruction(p.id)}
                        >
                          Remove
                        </button>
                      </TableCell>
                    </TableRow>
                    {revealed[p.id] && (
                      <TableRow>
                        <TableCell colSpan={5}>
                          <p className="text-body-sm text-mute">
                            {Object.entries(revealed[p.id])
                              .map(([k, v]) => `${k}: ${v}`)
                              .join(' · ') || '(no additional fields)'}
                          </p>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                ))}
              </TableBody>
            </Table>
          )}
          <form onSubmit={handleAddPaymentInstruction} className="flex flex-col gap-4">
            <div className={fieldRow}>
              <div className={fieldCol}>
                <Label>Label</Label>
                <Input required placeholder="Main account" value={payForm.label} onChange={(e) => setPayForm({ ...payForm, label: e.target.value })} />
              </div>
              <div className={fieldCol}>
                <Label>Method</Label>
                <select className={selectClass} value={payForm.method} onChange={(e) => setPayForm({ ...payForm, method: e.target.value })}>
                  {PAYMENT_METHODS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className={fieldRow}>
              <div className={fieldCol}>
                <Label>Provider (optional)</Label>
                <Input placeholder="e.g. RBC, Interac" value={payForm.provider} onChange={(e) => setPayForm({ ...payForm, provider: e.target.value })} />
              </div>
              <div className={fieldCol}>
                <Label>Currency</Label>
                <Input required value={payForm.currency} onChange={(e) => setPayForm({ ...payForm, currency: e.target.value.toUpperCase() })} />
              </div>
            </div>
            <div className={fieldCol}>
              <Label>Account holder (optional)</Label>
              <Input value={payForm.account_holder} onChange={(e) => setPayForm({ ...payForm, account_holder: e.target.value })} />
            </div>
            <div className="flex flex-col gap-2">
              <Label>Details (e.g. e-transfer email, account number)</Label>
              {payFields.map((f, i) => (
                <div key={i} className="flex gap-2">
                  <Input
                    placeholder="Field name"
                    value={f.key}
                    onChange={(e) => {
                      const next = [...payFields]
                      next[i] = { ...next[i], key: e.target.value }
                      setPayFields(next)
                    }}
                  />
                  <Input
                    placeholder="Value"
                    value={f.value}
                    onChange={(e) => {
                      const next = [...payFields]
                      next[i] = { ...next[i], value: e.target.value }
                      setPayFields(next)
                    }}
                  />
                  <button
                    type="button"
                    className="px-2 text-body-sm text-mute hover:text-ink"
                    onClick={() => setPayFields(payFields.filter((_, j) => j !== i))}
                  >
                    &times;
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="self-start text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
                onClick={() => setPayFields([...payFields, { key: '', value: '' }])}
              >
                + Add field
              </button>
            </div>
            <label className="flex items-center gap-2 text-body-sm text-ink">
              <input
                type="checkbox"
                className="size-4 accent-ink"
                checked={payForm.is_default}
                onChange={(e) => setPayForm({ ...payForm, is_default: e.target.checked })}
              />
              Set as default (used on new invoices)
            </label>
            {payError && <p className="text-body-sm text-negative">{payError}</p>}
            <Button type="submit" disabled={paySaving} className="self-start">
              {paySaving ? 'Saving…' : 'Add payment instruction'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Invoice template</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-body-sm text-mute">
            Choose which template new invoices use, or build your own: reorder the payment/notes sections, pick a
            font size, upload a logo. Import a template package (.json) someone shared with you, or export one of
            yours to share or back up.
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead></TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Accent</TableHead>
                <TableHead></TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {templates.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>
                    <input
                      type="radio"
                      name="default_template"
                      className="size-4 accent-ink"
                      checked={defaultTemplateId === t.id}
                      disabled={templateSaving !== null}
                      onChange={() => handleSetDefaultTemplate(t.id)}
                    />
                  </TableCell>
                  <TableCell>
                    {t.name} {t.is_system && <span className="text-caption text-mute">(system)</span>}
                  </TableCell>
                  <TableCell>
                    <span
                      className="inline-block size-3.5 rounded-sm align-middle"
                      style={{ background: t.theme.accent_color || '#1A365D' }}
                    />
                  </TableCell>
                  <TableCell>
                    <button
                      type="button"
                      className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
                      onClick={() => downloadFile(`/templates/${t.id}/export`, `${t.name}.tallyquo-template.json`)}
                    >
                      Export
                    </button>
                  </TableCell>
                  <TableCell>
                    {t.is_system ? (
                      <Link
                        className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
                        to={`/settings/templates/new?clone=${t.id}`}
                      >
                        Customize
                      </Link>
                    ) : (
                      <Link
                        className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
                        to={`/settings/templates/${t.id}/edit`}
                      >
                        Edit
                      </Link>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {templateError && <p className="text-body-sm text-negative">{templateError}</p>}
          <div className="flex items-center gap-4">
            <Link className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute" to="/settings/templates/new">
              + New custom template
            </Link>
            <input
              ref={importInputRef}
              type="file"
              accept="application/json"
              onChange={handleImportTemplate}
              className="text-body-sm text-mute file:mr-3 file:h-8 file:rounded-md file:border file:border-ink file:bg-canvas file:px-3 file:text-body-sm file:font-medium"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
