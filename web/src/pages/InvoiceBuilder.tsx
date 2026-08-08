import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'
import { todayLocal } from '../dateUtils'

interface Client {
  id: string
  legal_name: string
  country_code: string
  region_code: string | null
}

interface LineItem {
  description: string
  quantity: string
  unit: string
  unit_rate: string
  amount: string
}

interface TaxPreview {
  treatment: string
  jurisdiction: string | null
  lines: { label: string; amount: string; display_note: string | null }[]
  subtotal: string
  tax_total: string
  total: string
  warnings: string[]
}

const emptyLine = (): LineItem => ({ description: '', quantity: '1', unit: 'fixed', unit_rate: '', amount: '' })

export default function InvoiceBuilder() {
  const [clients, setClients] = useState<Client[]>([])
  const [clientId, setClientId] = useState('')
  const [invoiceDate, setInvoiceDate] = useState(todayLocal())
  const [currency, setCurrency] = useState('CAD')
  const [lines, setLines] = useState<LineItem[]>([emptyLine()])
  const [preview, setPreview] = useState<TaxPreview | null>(null)
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
  }, [])

  useEffect(() => {
    if (!clientId) return
    const validLines = lines.filter((l) => l.amount && !Number.isNaN(Number(l.amount)))
    if (validLines.length === 0) {
      setPreview(null)
      return
    }
    const timeout = setTimeout(() => {
      api
        .post<TaxPreview>('/invoices/preview-tax', {
          client_id: clientId,
          invoice_date: invoiceDate,
          line_items: validLines.map((l) => ({ amount: l.amount, is_taxable: true })),
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
  }, [clientId, invoiceDate, JSON.stringify(lines)])

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
        currency,
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

  return (
    <div>
      <h1>New invoice</h1>

      <div className="block">
        <div className="block-header">
          <h2>Client</h2>
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
            <div className="field-row">
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
              <div className="field">
                <label>Invoice date</label>
                <input type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} />
              </div>
              <div className="field">
                <label>Currency</label>
                <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  <option value="CAD">CAD</option>
                  <option value="USD">USD</option>
                </select>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="block">
        <div className="block-header">
          <h2>Line items</h2>
        </div>
        <div className="block-body">
          {lines.map((line, i) => (
            <div
              key={i}
              style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'flex-end' }}
            >
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

      <div className="block">
        <div className="block-header">
          <h2>Tax</h2>
        </div>
        <div className="block-body">
          {previewError && <p className="error-text">{previewError}</p>}
          {!preview && !previewError && <p className="caption">Add a client and a line item to see tax.</p>}
          {preview && (
            <div>
              <p style={{ marginBottom: 8 }}>
                <span className={`badge ${preview.treatment}`}>{preview.treatment.replace(/_/g, ' ')}</span>{' '}
                {preview.jurisdiction && <span className="caption">{preview.jurisdiction}</span>}
              </p>
              {preview.lines.map((l, i) => (
                <p key={i} className="caption">
                  {l.display_note ? `GST/HST: ${l.display_note}` : `${l.label}: ${currency} ${l.amount}`}
                </p>
              ))}
              {preview.warnings.map((w, i) => (
                <div key={i} className="block alert" style={{ marginTop: 8 }}>
                  <div className="block-body">{w}</div>
                </div>
              ))}
              <table style={{ marginTop: 12 }}>
                <tbody>
                  <tr>
                    <td>Subtotal</td>
                    <td className="amount">{currency} {preview.subtotal}</td>
                  </tr>
                  <tr>
                    <td>Tax</td>
                    <td className="amount">{currency} {preview.tax_total}</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Total</strong>
                    </td>
                    <td className="amount">
                      <strong>{currency} {preview.total}</strong>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {issueError && <p className="error-text">{issueError}</p>}
      <button
        className="primary"
        onClick={handleIssue}
        disabled={issuing || !preview || clients.length === 0}
        style={{ height: 40, paddingInline: 24 }}
      >
        {issuing ? 'Issuing…' : 'Issue invoice'}
      </button>
    </div>
  )
}
