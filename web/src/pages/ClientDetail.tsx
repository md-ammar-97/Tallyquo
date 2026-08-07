import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'

interface Client {
  id: string
  legal_name: string
  address_line1: string | null
  city: string | null
  region_code: string | null
  country_code: string
  tax_treatment: string
}

interface Period {
  period: string
  invoice_count: number
  billed_cad: string
  collected_cad: string
  outstanding_cad: string
}

interface Aging {
  bucket_0_30: string
  bucket_31_60: string
  bucket_61_90: string
  bucket_90_plus: string
}

interface Rollup {
  periods: Period[]
  aging: Aging
}

interface Invoice {
  id: string
  number: string | null
  status: string
  invoice_date: string | null
  currency: string
  total: string
}

const AGING_LABELS: [keyof Aging, string][] = [
  ['bucket_0_30', '0–30 days'],
  ['bucket_31_60', '31–60 days'],
  ['bucket_61_90', '61–90 days'],
  ['bucket_90_plus', '90+ days'],
]

export default function ClientDetail() {
  const { id } = useParams<{ id: string }>()
  const [client, setClient] = useState<Client | null>(null)
  const [rollup, setRollup] = useState<Rollup | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!id) return
    api
      .get<Client>(`/clients/${id}`)
      .then(setClient)
      .catch(() => setNotFound(true))
    api.get<Rollup>(`/clients/${id}/rollup`).then(setRollup)
    api.get<Invoice[]>(`/invoices?client_id=${id}`).then(setInvoices)
  }, [id])

  if (notFound) {
    return (
      <div>
        <h1>Client not found</h1>
        <Link to="/clients">Back to clients</Link>
      </div>
    )
  }
  if (!client) return null

  const totalOutstanding = rollup
    ? AGING_LABELS.reduce((sum, [key]) => sum + Number(rollup.aging[key]), 0)
    : 0

  return (
    <div>
      <h1>{client.legal_name}</h1>

      <div className="block">
        <div className="block-body">
          <p className="caption" style={{ marginBottom: 4 }}>
            {[client.address_line1, client.city, client.region_code, client.country_code]
              .filter(Boolean)
              .join(', ') || 'No address on file'}
          </p>
          <span className={`badge ${client.tax_treatment}`}>{client.tax_treatment.replace(/_/g, ' ')}</span>
        </div>
      </div>

      <div className="block">
        <div className="block-header">
          <h2>Period roll-up</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>Month</th>
              <th className="amount">Invoices</th>
              <th className="amount">Billed</th>
              <th className="amount">Collected</th>
              <th className="amount">Outstanding</th>
            </tr>
          </thead>
          <tbody>
            {rollup?.periods.map((p) => (
              <tr key={p.period}>
                <td>{p.period.slice(0, 7)}</td>
                <td className="amount">{p.invoice_count}</td>
                <td className="amount">CAD {p.billed_cad}</td>
                <td className="amount">CAD {p.collected_cad}</td>
                <td className="amount">CAD {p.outstanding_cad}</td>
              </tr>
            ))}
            {rollup && rollup.periods.length === 0 && (
              <tr>
                <td colSpan={5} className="caption" style={{ padding: 24 }}>
                  No issued invoices for this client yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="block">
        <div className="block-header">
          <h2>Aging</h2>
          <span className="caption">Total outstanding: CAD {totalOutstanding.toFixed(2)}</span>
        </div>
        <table>
          <thead>
            <tr>
              {AGING_LABELS.map(([, label]) => (
                <th key={label} className="amount">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {AGING_LABELS.map(([key]) => (
                <td key={key} className="amount">
                  CAD {rollup?.aging[key] ?? '0.00'}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      <div className="block">
        <div className="block-header">
          <h2>Invoices</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>Number</th>
              <th>Date</th>
              <th>Status</th>
              <th className="amount">Total</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id}>
                <td>
                  <Link to={`/invoices/${inv.id}`}>{inv.number ?? '(draft)'}</Link>
                </td>
                <td>{inv.invoice_date ?? '—'}</td>
                <td>
                  <span className={`badge ${inv.status}`}>{inv.status.replace(/_/g, ' ')}</span>
                </td>
                <td className="amount">
                  {inv.currency} {inv.total}
                </td>
              </tr>
            ))}
            {invoices.length === 0 && (
              <tr>
                <td colSpan={4} className="caption" style={{ padding: 24 }}>
                  No invoices for this client yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
