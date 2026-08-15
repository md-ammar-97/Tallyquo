import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { InvoiceStatusBadge } from '../components/InvoiceBadges'

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
      <div className="flex flex-col gap-4">
        <h1 className="font-display text-display-sm text-ink">Client not found</h1>
        <Link className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute" to="/clients">
          Back to clients
        </Link>
      </div>
    )
  }
  if (!client) return null

  const totalOutstanding = rollup
    ? AGING_LABELS.reduce((sum, [key]) => sum + Number(rollup.aging[key]), 0)
    : 0

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">{client.legal_name}</h1>

      <Card>
        <CardContent className="flex flex-col gap-2">
          <p className="text-body-sm text-mute">
            {[client.address_line1, client.city, client.region_code, client.country_code]
              .filter(Boolean)
              .join(', ') || 'No address on file'}
          </p>
          <Badge variant="secondary" className="w-fit capitalize">
            {client.tax_treatment.replace(/_/g, ' ')}
          </Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Period roll-up</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Month</TableHead>
                <TableHead className="text-right">Invoices</TableHead>
                <TableHead className="text-right">Billed</TableHead>
                <TableHead className="text-right">Collected</TableHead>
                <TableHead className="text-right">Outstanding</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rollup?.periods.map((p) => (
                <TableRow key={p.period}>
                  <TableCell>{p.period.slice(0, 7)}</TableCell>
                  <TableCell className="text-right">{p.invoice_count}</TableCell>
                  <TableCell className="text-right">CAD {p.billed_cad}</TableCell>
                  <TableCell className="text-right">CAD {p.collected_cad}</TableCell>
                  <TableCell className="text-right">CAD {p.outstanding_cad}</TableCell>
                </TableRow>
              ))}
              {rollup && rollup.periods.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-6 text-center text-body-sm text-mute">
                    No issued invoices for this client yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Aging</CardTitle>
          <span className="text-body-sm text-mute">Total outstanding: CAD {totalOutstanding.toFixed(2)}</span>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                {AGING_LABELS.map(([, label]) => (
                  <TableHead key={label} className="text-right">
                    {label}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                {AGING_LABELS.map(([key]) => (
                  <TableCell key={key} className="text-right">
                    CAD {rollup?.aging[key] ?? '0.00'}
                  </TableCell>
                ))}
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Invoices</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Number</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell>
                    <Link className="text-ink underline underline-offset-2 hover:text-mute" to={`/invoices/${inv.id}`}>
                      {inv.number ?? '(draft)'}
                    </Link>
                  </TableCell>
                  <TableCell>{inv.invoice_date ?? '—'}</TableCell>
                  <TableCell>
                    <InvoiceStatusBadge status={inv.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    {inv.currency} {inv.total}
                  </TableCell>
                </TableRow>
              ))}
              {invoices.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="py-6 text-center text-body-sm text-mute">
                    No invoices for this client yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
