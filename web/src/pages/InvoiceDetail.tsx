import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, API_BASE_URL, downloadFile } from '../api'
import { todayLocal } from '../dateUtils'
import InvoiceDocument, { type InvoiceDocumentData } from '../components/InvoiceDocument'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { InvoiceStatusBadge, TaxTreatmentBadge } from '../components/InvoiceBadges'

const selectClass = 'h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm'
const fieldCol = 'flex flex-1 flex-col gap-1.5'

interface LineItem {
  id: string
  description: string
  quantity: string
  unit: string
  unit_rate: string
  amount: string
}

interface Invoice {
  id: string
  client_id: string
  number: string | null
  status: string
  invoice_date: string | null
  due_date: string | null
  currency: string
  subtotal: string
  tax_total: string
  total: string
  amount_paid: string
  tax_treatment_snapshot: string | null
  total_cad: string | null
  fx_rate_to_cad: string | null
  fx_rate_date: string | null
  fx_rate_source: string | null
  has_share_link: boolean
  line_items: LineItem[]
}

interface Payment {
  id: string
  amount: string
  currency: string
  amount_cad: string | null
  fx_rate_to_cad: string | null
  fx_gain_loss: string | null
  received_date: string
  method: string | null
  reference: string | null
  note: string | null
}

interface EmailAccount {
  id: string
  label: string
  from_name: string
  from_address: string
  is_default: boolean
}

const emptyPaymentForm = { amount: '', received_date: todayLocal(), method: '', reference: '' }
const emptyRecurringForm = { cadence: 'monthly', day_of_period: '1', next_run_date: '', auto_issue: false }

function ChipInput({
  values,
  onChange,
  placeholder,
}: {
  values: string[]
  onChange: (values: string[]) => void
  placeholder?: string
}) {
  const [draft, setDraft] = useState('')

  function commit() {
    const trimmed = draft.trim()
    if (trimmed && !values.includes(trimmed)) onChange([...values, trimmed])
    setDraft('')
  }

  return (
    <div className="flex min-h-9 flex-wrap items-center gap-1 rounded-md border border-ink bg-canvas p-1">
      {values.map((v) => (
        <span key={v} className="flex items-center gap-1 rounded-sm bg-canvas-soft px-2 py-0.5 text-caption">
          {v}
          <button type="button" className="text-mute hover:text-ink" onClick={() => onChange(values.filter((x) => x !== v))}>
            &times;
          </button>
        </span>
      ))}
      <input
        className="h-6 min-w-[120px] flex-1 border-none bg-transparent px-1 text-body-sm outline-none"
        value={draft}
        placeholder={values.length === 0 ? placeholder : ''}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',' || e.key === 'Tab') {
            if (draft.trim()) e.preventDefault()
            commit()
          }
        }}
        onBlur={commit}
      />
    </div>
  )
}

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>()
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [doc, setDoc] = useState<InvoiceDocumentData | null>(null)
  const [payments, setPayments] = useState<Payment[]>([])
  const [notFound, setNotFound] = useState(false)
  const [form, setForm] = useState(emptyPaymentForm)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recurringForm, setRecurringForm] = useState(emptyRecurringForm)
  const [showRecurringForm, setShowRecurringForm] = useState(false)
  const [recurringSaving, setRecurringSaving] = useState(false)
  const [recurringError, setRecurringError] = useState<string | null>(null)
  const [recurringDone, setRecurringDone] = useState(false)
  const [shareToken, setShareToken] = useState<string | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const [showEmailModal, setShowEmailModal] = useState(false)
  const [emailAccounts, setEmailAccounts] = useState<EmailAccount[]>([])
  const [emailAccountId, setEmailAccountId] = useState('')
  const [emailTo, setEmailTo] = useState<string[]>([])
  const [emailCc, setEmailCc] = useState<string[]>([])
  const [emailSubject, setEmailSubject] = useState('')
  const [emailBody, setEmailBody] = useState('')
  const [attachPdf, setAttachPdf] = useState(true)
  const [extraFiles, setExtraFiles] = useState<File[]>([])
  const [emailSending, setEmailSending] = useState(false)
  const [emailError, setEmailError] = useState<string | null>(null)
  const [emailResult, setEmailResult] = useState<string | null>(null)

  function load() {
    if (!id) return
    api
      .get<Invoice>(`/invoices/${id}`)
      .then(setInvoice)
      .catch(() => setNotFound(true))
    api.get<InvoiceDocumentData>(`/invoices/${id}/document`).then(setDoc)
    api.get<Payment[]>(`/invoices/${id}/payments`).then(setPayments)
  }

  async function handleGetShareLink() {
    setShareError(null)
    try {
      const { token } = await api.post<{ token: string }>(`/invoices/${id}/share`)
      setShareToken(token)
    } catch (err) {
      setShareError(err instanceof ApiError ? err.message : 'Could not create share link.')
    }
  }

  async function handleRevokeShareLink() {
    await api.delete(`/invoices/${id}/share`)
    setShareToken(null)
    load()
  }

  function handleCopyShareLink() {
    if (!shareToken) return
    navigator.clipboard.writeText(`${window.location.origin}/share/${shareToken}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  async function handleOpenEmailModal() {
    setEmailError(null)
    setEmailResult(null)
    const accounts = await api.get<EmailAccount[]>('/email-accounts')
    setEmailAccounts(accounts)
    const defaultAccount = accounts.find((a) => a.is_default) ?? accounts[0]
    setEmailAccountId(defaultAccount?.id ?? '')

    let clientEmail = ''
    if (invoice) {
      try {
        const client = await api.get<{ email: string | null }>(`/clients/${invoice.client_id}`)
        clientEmail = client.email ?? ''
      } catch {
        // no-op -- To still starts empty and the user can type a recipient in
      }
    }
    setEmailTo(clientEmail ? [clientEmail] : [])
    setEmailCc([])
    setEmailSubject(invoice ? `Invoice ${invoice.number ?? ''}` : '')
    setEmailBody(
      invoice
        ? `Hi,\n\nPlease find invoice ${invoice.number ?? ''} attached, for a total of ${invoice.currency} ${invoice.total}.\n\nThanks,`
        : '',
    )
    setAttachPdf(true)
    setExtraFiles([])
    setShowEmailModal(true)
  }

  async function handleSendEmail(e: React.FormEvent) {
    e.preventDefault()
    // O5: a reminder-only email with nothing invoice-related attached is
    // legitimate, but never sent silently empty-handed -- confirmed explicitly.
    if (!attachPdf && extraFiles.length === 0) {
      if (!window.confirm('Send this email with no attachments?')) return
    }
    setEmailSending(true)
    setEmailError(null)
    setEmailResult(null)
    try {
      const body = new FormData()
      body.append('to_addresses', emailTo.join(','))
      body.append('cc_addresses', emailCc.join(','))
      body.append('subject', emailSubject)
      body.append('body', emailBody)
      body.append('attach_invoice_pdf', String(attachPdf))
      if (emailAccountId) body.append('email_account_id', emailAccountId)
      for (const file of extraFiles) body.append('extra_files', file)

      const token = localStorage.getItem('access_token')
      const res = await fetch(`${API_BASE_URL}/invoices/${id}/email`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body,
      })
      const data = await res.json()
      if (!res.ok) throw new ApiError(res.status, data.detail ?? 'Could not send this email.')

      if (data.status === 'failed') {
        setEmailError(data.error_detail ?? 'Could not send this email.')
      } else if (Object.keys(data.refused ?? {}).length > 0) {
        setEmailResult(
          `Sent to ${data.accepted.join(', ')}. Refused: ${Object.entries(data.refused)
            .map(([addr, reason]) => `${addr} (${reason})`)
            .join(', ')}`,
        )
      } else {
        setEmailResult(`Sent to ${data.accepted.join(', ')}.`)
        setShowEmailModal(false)
      }
    } catch (err) {
      setEmailError(err instanceof ApiError ? err.message : 'Could not send this email.')
    } finally {
      setEmailSending(false)
    }
  }

  useEffect(load, [id])

  async function handleRecordPayment(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.post(`/invoices/${id}/payments`, {
        amount: form.amount,
        received_date: form.received_date,
        method: form.method || null,
        reference: form.reference || null,
      })
      setForm(emptyPaymentForm)
      setShowForm(false)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not record payment.')
    } finally {
      setSaving(false)
    }
  }

  async function handleMakeRecurring(e: React.FormEvent) {
    e.preventDefault()
    setRecurringSaving(true)
    setRecurringError(null)
    try {
      await api.post('/recurring', {
        client_id: invoice!.client_id,
        source_invoice_id: id,
        cadence: recurringForm.cadence,
        day_of_period: recurringForm.day_of_period ? Number(recurringForm.day_of_period) : null,
        next_run_date: recurringForm.next_run_date,
        auto_issue: recurringForm.auto_issue,
      })
      setShowRecurringForm(false)
      setRecurringDone(true)
    } catch (err) {
      setRecurringError(err instanceof ApiError ? err.message : 'Could not create recurring rule.')
    } finally {
      setRecurringSaving(false)
    }
  }

  async function handleReverse(paymentId: string) {
    const reason = window.prompt('Reason for reversing this payment?')
    if (!reason) return
    await api.delete(`/invoices/payments/${paymentId}?reason=${encodeURIComponent(reason)}`)
    load()
  }

  async function handleCancel() {
    const reason = window.prompt('Reason for cancelling this invoice?')
    if (!reason) return
    await api.post(`/invoices/${id}/cancel?reason=${encodeURIComponent(reason)}`)
    load()
  }

  if (notFound) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="font-display text-display-sm text-ink">Invoice not found</h1>
        <Link className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute" to="/invoices">
          Back to invoices
        </Link>
      </div>
    )
  }
  if (!invoice) return null

  const canRecordPayment = ['issued', 'partially_paid', 'overdue'].includes(invoice.status)
  const canCancel = ['issued', 'partially_paid', 'overdue'].includes(invoice.status)

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">{invoice.number ?? '(draft)'}</h1>

      <Card>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            <InvoiceStatusBadge status={invoice.status} />
            {invoice.tax_treatment_snapshot && <TaxTreatmentBadge treatment={invoice.tax_treatment_snapshot} />}
          </div>
          <p className="text-body-sm text-mute">
            Invoice date: {invoice.invoice_date ?? '—'} · Due: {invoice.due_date ?? '—'} · Paid: {invoice.currency}{' '}
            {invoice.amount_paid}
          </p>
          {invoice.currency !== 'CAD' && (
            <p className="text-body-sm text-mute">
              {invoice.total_cad ? (
                <>
                  CAD {invoice.total_cad} at {invoice.fx_rate_to_cad} ({invoice.fx_rate_date})
                </>
              ) : (
                <span className="text-warning-content">
                  No CAD conversion available -- the FX rate source was unavailable at issue. Needs review.
                </span>
              )}
            </p>
          )}
          <div className="flex flex-wrap gap-3">
            {invoice.status !== 'draft' && (
              <Button variant="outline" onClick={() => downloadFile(`/invoices/${invoice.id}/pdf`, `${invoice.number}.pdf`)}>
                Download PDF
              </Button>
            )}
            {canCancel && (
              <Button variant="destructive" onClick={handleCancel}>
                Cancel invoice
              </Button>
            )}
            {invoice.status !== 'draft' && !recurringDone && (
              <Button variant="outline" onClick={() => setShowRecurringForm((s) => !s)}>
                {showRecurringForm ? 'Cancel' : 'Make recurring'}
              </Button>
            )}
            {recurringDone && <span className="self-center text-body-sm text-mute">Recurring rule created.</span>}
            {invoice.status !== 'draft' && !shareToken && (
              <Button variant="outline" onClick={handleGetShareLink}>
                {invoice.has_share_link ? 'View shareable link' : 'Get shareable link'}
              </Button>
            )}
            {invoice.status !== 'draft' && <Button variant="outline" onClick={handleOpenEmailModal}>Email invoice</Button>}
          </div>
          {shareError && <p className="text-body-sm text-negative">{shareError}</p>}
          {emailResult && <p className="text-body-sm text-mute">{emailResult}</p>}
          {shareToken && (
            <div className="flex items-center gap-2 border-t border-divider pt-4">
              <Input readOnly value={`${window.location.origin}/share/${shareToken}`} className="flex-1" />
              <Button variant="outline" onClick={handleCopyShareLink}>{copied ? 'Copied!' : 'Copy'}</Button>
              <Button variant="destructive" onClick={handleRevokeShareLink}>
                Revoke
              </Button>
            </div>
          )}
          {showRecurringForm && (
            <form onSubmit={handleMakeRecurring} className="flex flex-col gap-4 border-t border-divider pt-4">
              <div className="flex flex-wrap gap-4">
                <div className={fieldCol}>
                  <Label>Cadence</Label>
                  <select
                    className={selectClass}
                    value={recurringForm.cadence}
                    onChange={(e) => setRecurringForm({ ...recurringForm, cadence: e.target.value })}
                  >
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Biweekly</option>
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="semiannual">Semiannual</option>
                    <option value="annual">Annual</option>
                  </select>
                </div>
                <div className={fieldCol}>
                  <Label>Next run date</Label>
                  <Input
                    type="date"
                    required
                    value={recurringForm.next_run_date}
                    onChange={(e) => setRecurringForm({ ...recurringForm, next_run_date: e.target.value })}
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-body-sm text-ink">
                <input
                  type="checkbox"
                  className="size-4 accent-ink"
                  checked={recurringForm.auto_issue}
                  onChange={(e) => setRecurringForm({ ...recurringForm, auto_issue: e.target.checked })}
                />
                Auto-issue (default: create a draft and leave it for you to review)
              </label>
              {recurringError && <p className="text-body-sm text-negative">{recurringError}</p>}
              <Button type="submit" disabled={recurringSaving} className="self-start">
                {recurringSaving ? 'Saving…' : 'Create recurring rule'}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      {doc && (
        <Card>
          <CardContent>
            <InvoiceDocument data={doc} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Payments</CardTitle>
          {canRecordPayment && (
            <Button onClick={() => setShowForm((s) => !s)}>{showForm ? 'Cancel' : 'Record payment'}</Button>
          )}
        </CardHeader>
        {showForm && (
          <CardContent className="border-b border-divider pb-6">
            <form onSubmit={handleRecordPayment} className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-4">
                <div className={fieldCol}>
                  <Label>Amount</Label>
                  <Input required value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="0.00" />
                </div>
                <div className={fieldCol}>
                  <Label>Received date</Label>
                  <Input required type="date" value={form.received_date} onChange={(e) => setForm({ ...form, received_date: e.target.value })} />
                </div>
              </div>
              <div className="flex flex-wrap gap-4">
                <div className={fieldCol}>
                  <Label>Method (optional)</Label>
                  <Input value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })} />
                </div>
                <div className={fieldCol}>
                  <Label>Reference (optional)</Label>
                  <Input value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
                </div>
              </div>
              {error && <p className="text-body-sm text-negative">{error}</p>}
              <Button type="submit" disabled={saving} className="self-start">
                {saving ? 'Saving…' : 'Record payment'}
              </Button>
            </form>
          </CardContent>
        )}
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Method</TableHead>
                <TableHead>Reference</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                {invoice.currency !== 'CAD' && <TableHead className="text-right">FX gain/loss</TableHead>}
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.received_date}</TableCell>
                  <TableCell>{p.method ?? '—'}</TableCell>
                  <TableCell>{p.reference ?? '—'}</TableCell>
                  <TableCell className="text-right">
                    {p.currency} {p.amount}
                    {p.currency !== 'CAD' && p.amount_cad && <span className="text-caption text-mute"> (CAD {p.amount_cad})</span>}
                  </TableCell>
                  {invoice.currency !== 'CAD' && (
                    <TableCell className="text-right">
                      {p.fx_gain_loss === null ? '—' : `${Number(p.fx_gain_loss) >= 0 ? '+' : ''}${p.fx_gain_loss}`}
                    </TableCell>
                  )}
                  <TableCell>
                    <Button variant="destructive" size="sm" onClick={() => handleReverse(p.id)}>
                      Reverse
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {payments.length === 0 && (
                <TableRow>
                  <TableCell colSpan={invoice.currency !== 'CAD' ? 6 : 5} className="py-6 text-center text-body-sm text-mute">
                    No payments recorded yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={showEmailModal} onOpenChange={setShowEmailModal}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-display text-display-xs font-semibold text-ink">Email invoice</DialogTitle>
          </DialogHeader>
          {emailAccounts.length === 0 ? (
            <div className="flex flex-col gap-3">
              <p className="text-body-sm text-mute">
                No email account configured yet.{' '}
                <Link to="/settings/email-accounts" className="font-medium text-ink underline underline-offset-2 hover:text-mute">
                  Add one
                </Link>{' '}
                to send from your own address.
              </p>
              <Button variant="outline" className="self-start" onClick={() => setShowEmailModal(false)}>
                Close
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSendEmail} className="flex flex-col gap-4">
              <div className={fieldCol}>
                <Label>From</Label>
                <select className={selectClass} value={emailAccountId} onChange={(e) => setEmailAccountId(e.target.value)}>
                  {emailAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.label} ({a.from_address})
                    </option>
                  ))}
                </select>
              </div>
              <div className={fieldCol}>
                <Label>To</Label>
                <ChipInput values={emailTo} onChange={setEmailTo} placeholder="client@example.com" />
              </div>
              <div className={fieldCol}>
                <Label>Cc</Label>
                <ChipInput values={emailCc} onChange={setEmailCc} placeholder="optional" />
              </div>
              <div className={fieldCol}>
                <Label>Subject</Label>
                <Input required value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} />
              </div>
              <div className={fieldCol}>
                <Label>Body</Label>
                <Textarea required rows={8} value={emailBody} onChange={(e) => setEmailBody(e.target.value)} />
              </div>
              <div className={fieldCol}>
                <Label>Attachments</Label>
                <div className="flex flex-wrap gap-1">
                  <span className="flex items-center gap-1 rounded-sm bg-canvas-soft px-2 py-0.5 text-caption">
                    {attachPdf ? '📎 ' : ''}
                    {invoice.number ?? 'invoice'}.pdf
                    <button type="button" className="text-mute hover:text-ink" onClick={() => setAttachPdf((v) => !v)}>
                      {attachPdf ? '×' : '+'}
                    </button>
                  </span>
                  {extraFiles.map((f, i) => (
                    <span key={i} className="flex items-center gap-1 rounded-sm bg-canvas-soft px-2 py-0.5 text-caption">
                      {f.name}
                      <button
                        type="button"
                        className="text-mute hover:text-ink"
                        onClick={() => setExtraFiles((files) => files.filter((_, idx) => idx !== i))}
                      >
                        &times;
                      </button>
                    </span>
                  ))}
                </div>
                <label className="mt-1 inline-block">
                  <input
                    type="file"
                    multiple
                    className="hidden"
                    onChange={(e) => setExtraFiles((files) => [...files, ...Array.from(e.target.files ?? [])])}
                  />
                  <span className="cursor-pointer text-caption font-medium text-ink underline underline-offset-2 hover:text-mute">
                    + Add attachment
                  </span>
                </label>
              </div>
              {emailError && <p className="text-body-sm text-negative">{emailError}</p>}
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowEmailModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={emailSending || emailTo.length === 0}>
                  {emailSending ? 'Sending…' : 'Send'}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
