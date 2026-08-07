import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { API_BASE_URL } from '../api'

interface LineItem {
  id: string
  description: string
  quantity: string
  unit_rate: string
  amount: string
}

interface Invoice {
  id: string
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
  line_items: LineItem[]
}

export default function PublicInvoice() {
  const { token } = useParams<{ token: string }>()
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!token) return
    fetch(`${API_BASE_URL}/public/invoices/${token}`)
      .then((res) => {
        if (!res.ok) throw new Error('not found')
        return res.json()
      })
      .then(setInvoice)
      .catch(() => setNotFound(true))
  }, [token])

  async function handleDownload() {
    const res = await fetch(`${API_BASE_URL}/public/invoices/${token}/pdf`)
    if (!res.ok) return
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${invoice?.number ?? 'invoice'}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  if (notFound) {
    return (
      <main style={{ display: 'flex', minHeight: '100vh', alignItems: 'center', justifyContent: 'center' }}>
        <div className="block" style={{ width: 400 }}>
          <div className="block-body">
            <p>This link is no longer valid, or the invoice doesn't exist.</p>
          </div>
        </div>
      </main>
    )
  }
  if (!invoice) return null

  return (
    <main style={{ display: 'flex', justifyContent: 'center', padding: 'var(--space-6) var(--space-4)' }}>
      <div style={{ width: '100%', maxWidth: 640 }}>
        <h1>{invoice.number}</h1>
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
            <table style={{ marginTop: 16 }}>
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
            <button className="primary" style={{ marginTop: 16 }} onClick={handleDownload}>
              Download PDF
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}
