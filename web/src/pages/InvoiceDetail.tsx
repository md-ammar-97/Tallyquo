import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, API_BASE_URL, downloadFile } from '../api'

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

const emptyPaymentForm = { amount: '', received_date: new Date().toISOString().slice(0, 10), method: '', reference: '' }
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
    <div className="chip-input">
      {values.map((v) => (
        <span key={v} className="chip">
          {v}
          <button type="button" onClick={() => onChange(values.filter((x) => x !== v))}>
            &times;
          </button>
        </span>
      ))}
      <input
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
      <div>
        <h1>Invoice not found</h1>
        <Link to="/invoices">Back to invoices</Link>
      </div>
    )
  }
  if (!invoice) return null

  const canRecordPayment = ['issued', 'partially_paid', 'overdue'].includes(invoice.status)
  const canCancel = ['issued', 'partially_paid', 'overdue'].includes(invoice.status)

  return (
    <div>
      <h1>{invoice.number ?? '(draft)'}</h1>

      <div className="block">
        <div className="block-body">
          <p style={{ marginBottom: 8 }}>
            <span className={`badge ${invoice.status}`}>{invoice.status.replace(/_/g, ' ')}</span>{' '}
            {invoice.tax_treatment_snapshot && (
              <span className={`badge ${invoice.tax_treatment_snapshot}`}>
                {invoice.tax_treatment_snapshot.replace(/_/g, ' ')}
              </span>
            )}
          </p>
          <p className="caption">
            Invoice date: {invoice.invoice_date ?? '—'} · Due: {invoice.due_date ?? '—'}
          </p>
          <table style={{ marginTop: 12 }}>
            <tbody>
              <tr>
                <td>Subtotal</td>
                <td className="amount">
                  {invoice.currency} {invoice.subtotal}
                </td>
              </tr>
              <tr>
                <td>Tax</td>
                <td className="amount">
                  {invoice.currency} {invoice.tax_total}
                </td>
              </tr>
              <tr>
                <td>
                  <strong>Total</strong>
                </td>
                <td className="amount">
                  <strong>
                    {invoice.currency} {invoice.total}
                  </strong>
                </td>
              </tr>
              <tr>
                <td>Paid</td>
                <td className="amount">
                  {invoice.currency} {invoice.amount_paid}
                </td>
              </tr>
            </tbody>
          </table>
          {invoice.currency !== 'CAD' && (
            <p className="caption" style={{ marginTop: 8 }}>
              {invoice.total_cad ? (
                <>
                  CAD {invoice.total_cad} at {invoice.fx_rate_to_cad} ({invoice.fx_rate_date})
                </>
              ) : (
                <span style={{ color: 'var(--color-status-attention)' }}>
                  No CAD conversion available -- the FX rate source was unavailable at issue. Needs review.
                </span>
              )}
            </p>
          )}
          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            {invoice.status !== 'draft' && (
              <button onClick={() => downloadFile(`/invoices/${invoice.id}/pdf`, `${invoice.number}.pdf`)}>
                Download PDF
              </button>
            )}
            {canCancel && (
              <button className="danger" onClick={handleCancel}>
                Cancel invoice
              </button>
            )}
            {invoice.status !== 'draft' && !recurringDone && (
              <button onClick={() => setShowRecurringForm((s) => !s)}>
                {showRecurringForm ? 'Cancel' : 'Make recurring'}
              </button>
            )}
            {recurringDone && <span className="caption">Recurring rule created.</span>}
            {invoice.status !== 'draft' && !shareToken && (
              <button onClick={handleGetShareLink}>
                {invoice.has_share_link ? 'View shareable link' : 'Get shareable link'}
              </button>
            )}
            {invoice.status !== 'draft' && <button onClick={handleOpenEmailModal}>Email invoice</button>}
          </div>
          {shareError && <p className="error-text">{shareError}</p>}
          {emailResult && <p className="caption">{emailResult}</p>}
          {shareToken && (
            <div
              style={{
                marginTop: 16,
                paddingTop: 16,
                borderTop: '1px solid var(--color-border-default)',
                display: 'flex',
                gap: 8,
                alignItems: 'center',
              }}
            >
              <input readOnly value={`${window.location.origin}/share/${shareToken}`} style={{ flex: 1 }} />
              <button onClick={handleCopyShareLink}>{copied ? 'Copied!' : 'Copy'}</button>
              <button className="danger" onClick={handleRevokeShareLink}>
                Revoke
              </button>
            </div>
          )}
          {showRecurringForm && (
            <form
              onSubmit={handleMakeRecurring}
              style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--color-border-default)' }}
            >
              <div className="field-row">
                <div className="field">
                  <label>Cadence</label>
                  <select
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
                <div className="field">
                  <label>Next run date</label>
                  <input
                    type="date"
                    required
                    value={recurringForm.next_run_date}
                    onChange={(e) => setRecurringForm({ ...recurringForm, next_run_date: e.target.value })}
                  />
                </div>
              </div>
              <div className="field">
                <label>
                  <input
                    type="checkbox"
                    style={{ width: 'auto', marginRight: 8 }}
                    checked={recurringForm.auto_issue}
                    onChange={(e) => setRecurringForm({ ...recurringForm, auto_issue: e.target.checked })}
                  />
                  Auto-issue (default: create a draft and leave it for you to review)
                </label>
              </div>
              {recurringError && <p className="error-text">{recurringError}</p>}
              <button type="submit" className="primary" disabled={recurringSaving}>
                {recurringSaving ? 'Saving…' : 'Create recurring rule'}
              </button>
            </form>
          )}
        </div>
      </div>

      <div className="block">
        <div className="block-header">
          <h2>Line items</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>Description</th>
              <th className="amount">Qty</th>
              <th className="amount">Rate</th>
              <th className="amount">Amount</th>
            </tr>
          </thead>
          <tbody>
            {invoice.line_items.map((li) => (
              <tr key={li.id}>
                <td>{li.description}</td>
                <td className="amount">{li.quantity}</td>
                <td className="amount">{li.unit_rate}</td>
                <td className="amount">{li.amount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="block">
        <div className="block-header">
          <h2>Payments</h2>
          {canRecordPayment && (
            <button className="primary" onClick={() => setShowForm((s) => !s)}>
              {showForm ? 'Cancel' : 'Record payment'}
            </button>
          )}
        </div>
        {showForm && (
          <div className="block-body" style={{ borderBottom: '1px solid var(--color-border-default)' }}>
            <form onSubmit={handleRecordPayment}>
              <div className="field-row">
                <div className="field">
                  <label>Amount</label>
                  <input
                    required
                    value={form.amount}
                    onChange={(e) => setForm({ ...form, amount: e.target.value })}
                    placeholder="0.00"
                  />
                </div>
                <div className="field">
                  <label>Received date</label>
                  <input
                    required
                    type="date"
                    value={form.received_date}
                    onChange={(e) => setForm({ ...form, received_date: e.target.value })}
                  />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Method (optional)</label>
                  <input value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })} />
                </div>
                <div className="field">
                  <label>Reference (optional)</label>
                  <input value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
                </div>
              </div>
              {error && <p className="error-text">{error}</p>}
              <button type="submit" className="primary" disabled={saving}>
                {saving ? 'Saving…' : 'Record payment'}
              </button>
            </form>
          </div>
        )}
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Method</th>
              <th>Reference</th>
              <th className="amount">Amount</th>
              {invoice.currency !== 'CAD' && <th className="amount">FX gain/loss</th>}
              <th></th>
            </tr>
          </thead>
          <tbody>
            {payments.map((p) => (
              <tr key={p.id}>
                <td>{p.received_date}</td>
                <td>{p.method ?? '—'}</td>
                <td>{p.reference ?? '—'}</td>
                <td className="amount">
                  {p.currency} {p.amount}
                  {p.currency !== 'CAD' && p.amount_cad && (
                    <span className="caption"> (CAD {p.amount_cad})</span>
                  )}
                </td>
                {invoice.currency !== 'CAD' && (
                  <td className="amount">
                    {p.fx_gain_loss === null
                      ? '—'
                      : `${Number(p.fx_gain_loss) >= 0 ? '+' : ''}${p.fx_gain_loss}`}
                  </td>
                )}
                <td>
                  <button className="danger" onClick={() => handleReverse(p.id)}>
                    Reverse
                  </button>
                </td>
              </tr>
            ))}
            {payments.length === 0 && (
              <tr>
                <td colSpan={invoice.currency !== 'CAD' ? 6 : 5} className="caption" style={{ padding: 24 }}>
                  No payments recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showEmailModal && (
        <div className="modal-backdrop" onClick={() => setShowEmailModal(false)}>
          <div className="block modal" onClick={(e) => e.stopPropagation()}>
            <div className="block-header">
              <h2>Email invoice</h2>
            </div>
            {emailAccounts.length === 0 ? (
              <div className="block-body">
                <p className="caption">
                  No email account configured yet.{' '}
                  <Link to="/email-accounts" style={{ color: 'var(--color-text-link)' }}>
                    Add one
                  </Link>{' '}
                  to send from your own address.
                </p>
                <button onClick={() => setShowEmailModal(false)} style={{ marginTop: 12 }}>
                  Close
                </button>
              </div>
            ) : (
              <form onSubmit={handleSendEmail} style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <div className="block-body">
                  <div className="field">
                    <label>From</label>
                    <select value={emailAccountId} onChange={(e) => setEmailAccountId(e.target.value)}>
                      {emailAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.label} ({a.from_address})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>To</label>
                    <ChipInput values={emailTo} onChange={setEmailTo} placeholder="client@example.com" />
                  </div>
                  <div className="field">
                    <label>Cc</label>
                    <ChipInput values={emailCc} onChange={setEmailCc} placeholder="optional" />
                  </div>
                  <div className="field">
                    <label>Subject</label>
                    <input required value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} />
                  </div>
                  <div className="field">
                    <label>Body</label>
                    <textarea
                      required
                      rows={8}
                      value={emailBody}
                      onChange={(e) => setEmailBody(e.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label>Attachments</label>
                    <div>
                      <span className="chip">
                        {attachPdf ? '📎 ' : ''}
                        {invoice.number ?? 'invoice'}.pdf
                        <button type="button" onClick={() => setAttachPdf((v) => !v)}>
                          {attachPdf ? '×' : '+'}
                        </button>
                      </span>
                      {extraFiles.map((f, i) => (
                        <span key={i} className="chip">
                          {f.name}
                          <button
                            type="button"
                            onClick={() => setExtraFiles((files) => files.filter((_, idx) => idx !== i))}
                          >
                            &times;
                          </button>
                        </span>
                      ))}
                    </div>
                    <label style={{ display: 'inline-block', marginTop: 8 }}>
                      <input
                        type="file"
                        multiple
                        style={{ display: 'none' }}
                        onChange={(e) =>
                          setExtraFiles((files) => [...files, ...Array.from(e.target.files ?? [])])
                        }
                      />
                      <span style={{ color: 'var(--color-text-link)', cursor: 'pointer', fontSize: 12 }}>
                        + Add attachment
                      </span>
                    </label>
                  </div>
                  {emailError && <p className="error-text">{emailError}</p>}
                </div>
                <div className="modal-footer">
                  <button type="button" onClick={() => setShowEmailModal(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="primary" disabled={emailSending || emailTo.length === 0}>
                    {emailSending ? 'Sending…' : 'Send'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
