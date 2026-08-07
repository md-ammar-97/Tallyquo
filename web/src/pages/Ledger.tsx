import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadFile } from '../api'

interface Invoice {
  id: string
  number: string | null
  status: string
  invoice_date: string | null
  currency: string
  total: string
  tax_treatment_snapshot: string | null
}

export default function Ledger() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => {
    const query = statusFilter ? `?status=${statusFilter}` : ''
    api.get<Invoice[]>(`/invoices${query}`).then(setInvoices)
  }, [statusFilter])

  return (
    <div>
      <h1>Invoices</h1>

      <div className="block">
        <div className="block-header">
          <h2>Ledger</h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="issued">Issued</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <button onClick={() => downloadFile('/invoices/export.csv', 'invoices.csv')}>Export CSV</button>
            <Link to="/invoices/new">
              <button className="primary">New invoice</button>
            </Link>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Number</th>
              <th>Date</th>
              <th>Status</th>
              <th>Tax</th>
              <th className="amount">Total</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.number ?? '(draft)'}</td>
                <td>{inv.invoice_date ?? '—'}</td>
                <td>
                  <span className={`badge ${inv.status}`}>{inv.status}</span>
                </td>
                <td>
                  {inv.tax_treatment_snapshot && (
                    <span className={`badge ${inv.tax_treatment_snapshot}`}>
                      {inv.tax_treatment_snapshot.replace(/_/g, ' ')}
                    </span>
                  )}
                </td>
                <td className="amount">
                  {inv.currency} {inv.total}
                </td>
                <td>
                  {inv.status !== 'draft' && (
                    <button onClick={() => downloadFile(`/invoices/${inv.id}/pdf`, `${inv.number}.pdf`)}>
                      PDF
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {invoices.length === 0 && (
              <tr>
                <td colSpan={6} className="caption" style={{ padding: 24 }}>
                  No invoices yet. Add a client, then bill them -- most people are done in about two minutes.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
