import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'
import { todayLocal } from '../dateUtils'
import InvoiceDocument, { type InvoiceDocumentData } from '../components/InvoiceDocument'
import ComplianceChecklist, { type ComplianceProfile } from '../components/ComplianceChecklist'

interface Client {
  id: string
  legal_name: string
  country_code: string
  region_code: string | null
  address_line1: string | null
  city: string | null
}

interface LineItem {
  description: string
  quantity: string
  unit: string
  unit_rate: string
  amount: string
}

interface DocumentPreview extends InvoiceDocumentData {
  warnings: string[]
}

const TERMS_OPTIONS = [
  { label: 'Due on receipt', days: 0 },
  { label: 'Net 15', days: 15 },
  { label: 'Net 30', days: 30 },
  { label: 'Net 45', days: 45 },
  { label: 'Net 60', days: 60 },
]

const emptyLine = (): LineItem => ({ description: '', quantity: '1', unit: 'fixed', unit_rate: '', amount: '' })

function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr + 'T00:00:00')
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export default function InvoiceBuilder() {
  const [clients, setClients] = useState<Client[]>([])
  const [clientId, setClientId] = useState('')
  const [invoiceDate, setInvoiceDate] = useState(todayLocal())
  const [currency, setCurrency] = useState('CAD')
  const [termsDays, setTermsDays] = useState(30)
  const [dueDate, setDueDate] = useState(addDays(todayLocal(), 30))
  const [servicePeriodStart, setServicePeriodStart] = useState('')
  const [servicePeriodEnd, setServicePeriodEnd] = useState('')
  const [poReference, setPoReference] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<LineItem[]>([emptyLine()])

  const [profile, setProfile] = useState<ComplianceProfile | null>(null)
  const [preview, setPreview] = useState<DocumentPreview | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)

  const [issuing, setIssuing] = useState(false)
  const [issueError, setIssueError] = useState<string | null>(null)
  const [issuedInvoice, setIssuedInvoice] = useState<{ id: string; number: string; total: string } | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.get<Client[]>('/clients').then((cs) => {
      setClients(cs)
      if (cs.length > 0) setClientId(cs[0].id)
    })
    api.get<ComplianceProfile>('/profile').then(setProfile).catch(() => setProfile(null))
  }, [])

  function handleTermsChange(days: number) {
    setTermsDays(days)
    setDueDate(addDays(invoiceDate, days))
  }

  function handleInvoiceDateChange(value: string) {
    setInvoiceDate(value)
    setDueDate(addDays(value, termsDays))
  }

  useEffect(() => {
    if (!clientId) return
    const validLines = lines.filter((l) => l.amount && !Number.isNaN(Number(l.amount)))
    if (validLines.length === 0) {
      setPreview(null)
      return
    }
    const timeout = setTimeout(() => {
      api
        .post<DocumentPreview>('/invoices/preview-document', {
          client_id: clientId,
          invoice_date: invoiceDate,
          due_date: dueDate || null,
          service_period_start: servicePeriodStart || null,
          service_period_end: servicePeriodEnd || null,
          currency,
          po_reference: poReference || null,
          notes: notes || null,
          line_items: validLines.map((l) => ({
            description: l.description || '(no description)',
            quantity: l.quantity,
            unit: l.unit,
            unit_rate: l.unit_rate || l.amount,
            amount: l.amount,
          })),
        })
        .then((p) => {
          setPreview(p)
          setPreviewError(null)
        })
        .catch((err) => {
          setPreview(null)
          setPreviewError(err instanceof ApiError ? err.message : 'Could not compute tax.')
        })
    }, 300)
    return () => clearTimeout(timeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, invoiceDate, dueDate, servicePeriodStart, servicePeriodEnd, currency, poReference, notes, JSON.stringify(lines)])

  function updateLine(i: number, patch: Partial<LineItem>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }

  function addLine() {
    setLines((prev) => [...prev, emptyLine()])
  }

  function removeLine(i: number) {
    setLines((prev) => prev.filter((_, idx) => idx !== i))
  }

  async function handleIssue() {
    setIssuing(true)
    setIssueError(null)
    try {
      const draft = await api.post<{ id: string }>('/invoices', {
        client_id: clientId,
        invoice_date: invoiceDate,
        due_date: dueDate || null,
        payment_terms_days: termsDays,
        service_period_start: servicePeriodStart || null,
        service_period_end: servicePeriodEnd || null,
        currency,
        po_reference: poReference || null,
        notes: notes || null,
        line_items: lines
          .filter((l) => l.amount)
          .map((l) => ({
            description: l.description || '(no description)',
            quantity: l.quantity,
            unit: l.unit,
            unit_rate: l.unit_rate || l.amount,
            amount: l.amount,
          })),
      })
      const issued = await api.post<{ id: string; number: string; total: string }>(
        `/invoices/${draft.id}/issue`,
        {},
      )
      setIssuedInvoice(issued)
    } catch (err) {
      setIssueError(err instanceof ApiError ? err.message : 'Could not issue invoice.')
    } finally {
      setIssuing(false)
    }
  }

  if (issuedInvoice) {
    return (
      <div>
        <h1>Invoice issued</h1>
        <div className="block">
          <div className="block-body">
            <p style={{ marginBottom: 8 }}>
              <span className="badge issued">Issued</span>
            </p>
            <h2>{issuedInvoice.number}</h2>
            <p className="caption" style={{ margin: '8px 0 16px' }}>
              Total: {currency} {issuedInvoice.total}
            </p>
            <button
              className="primary"
              onClick={() => downloadFile(`/invoices/${issuedInvoice.id}/pdf`, `${issuedInvoice.number}.pdf`)}
            >
              Download PDF
            </button>{' '}
            <button
              onClick={() => {
                setIssuedInvoice(null)
                setLines([emptyLine()])
              }}
            >
              Create another
            </button>{' '}
            <button onClick={() => navigate('/invoices')}>View ledger</button>
          </div>
        </div>
      </div>
    )
  }

  const selectedClient = clients.find((c) => c.id === clientId) || null

  return (
    <div>
      <h1>New invoice</h1>

      <div className="invoice-builder-layout">
        <div>
          <div className="block">
            <div className="block-header">
              <h2>Invoice details</h2>
            </div>
            <div className="block-body">
              {clients.length === 0 ? (
                <p className="caption">
                  No clients yet.{' '}
                  <a href="/clients" style={{ color: 'var(--color-text-link)' }}>
                    Add a client
                  </a>{' '}
                  first.
                </p>
              ) : (
                <>
                  <div className="field">
                    <label>Client</label>
                    <select value={clientId} onChange={(e) => setClientId(e.target.value)}>
                      {clients.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.legal_name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field-row">
                    <div className="field">
                      <label>Issue date</label>
                      <input type="date" value={invoiceDate} onChange={(e) => handleInvoiceDateChange(e.target.value)} />
                    </div>
                    <div className="field">
                      <label>Due date</label>
                      <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
                    </div>
                  </div>
                  <div className="field-row">
                    <div className="field">
                      <label>Terms</label>
                      <select value={termsDays} onChange={(e) => handleTermsChange(Number(e.target.value))}>
                        {TERMS_OPTIONS.map((t) => (
                          <option key={t.days} value={t.days}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label>Currency</label>
                      <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                        <option value="CAD">CAD</option>
                        <option value="USD">USD</option>
                      </select>
                    </div>
                  </div>
                  <div className="field-row">
                    <div className="field">
                      <label>Service period start (optional)</label>
                      <input
                        type="date"
                        value={servicePeriodStart}
                        onChange={(e) => setServicePeriodStart(e.target.value)}
                      />
                    </div>
                    <div className="field">
                      <label>Service period end (optional)</label>
                      <input type="date" value={servicePeriodEnd} onChange={(e) => setServicePeriodEnd(e.target.value)} />
                    </div>
                  </div>
                  <div className="field">
                    <label>PO reference (optional)</label>
                    <input value={poReference} onChange={(e) => setPoReference(e.target.value)} />
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="block">
            <div className="block-header">
              <h2>Line items</h2>
            </div>
            <div className="block-body">
              {lines.map((line, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'flex-end' }}>
                  <div className="field" style={{ flex: 3, marginBottom: 0 }}>
                    {i === 0 && <label>Description</label>}
                    <input
                      value={line.description}
                      onChange={(e) => updateLine(i, { description: e.target.value })}
                      placeholder="Consulting services"
                    />
                  </div>
                  <div className="field" style={{ flex: 1, marginBottom: 0 }}>
                    {i === 0 && <label>Qty</label>}
                    <input value={line.quantity} onChange={(e) => updateLine(i, { quantity: e.target.value })} />
                  </div>
                  <div className="field" style={{ flex: 1, marginBottom: 0 }}>
                    {i === 0 && <label>Amount</label>}
                    <input
                      value={line.amount}
                      onChange={(e) => updateLine(i, { amount: e.target.value, unit_rate: e.target.value })}
                      placeholder="0.00"
                    />
                  </div>
                  <button onClick={() => removeLine(i)} disabled={lines.length === 1} style={{ flexShrink: 0 }}>
                    &times;
                  </button>
                </div>
              ))}
              <button onClick={addLine}>+ Add line</button>
            </div>
          </div>

          <div className="field">
            <label>Notes (optional, shown on invoice)</label>
            <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>

          {previewError && (
            <div className="block alert">
              <div className="block-body">{previewError}</div>
            </div>
          )}
          {preview?.warnings.map((w, i) => (
            <div key={i} className="block alert">
              <div className="block-body">{w}</div>
            </div>
          ))}

          <ComplianceChecklist
            profile={profile}
            client={selectedClient}
            taxReady={!!preview && !previewError}
          />

          {issueError && <p className="error-text">{issueError}</p>}
          <button
            className="primary"
            onClick={handleIssue}
            disabled={issuing || !preview || clients.length === 0}
            style={{ height: 40, paddingInline: 24, marginTop: 16 }}
          >
            {issuing ? 'Issuing…' : 'Issue invoice'}
          </button>
        </div>

        <div className="block invoice-builder-preview">
          <div className="block-header">
            <h2>Preview</h2>
          </div>
          <div className="block-body">
            {preview ? (
              <InvoiceDocument data={preview} />
            ) : (
              <p className="caption">Add a client and a line item to see the invoice preview.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
