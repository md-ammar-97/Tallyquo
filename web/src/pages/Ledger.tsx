import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadFile } from '../api'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { InvoiceStatusBadge, TaxTreatmentBadge } from '../components/InvoiceBadges'

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
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">Invoices</h1>

      <Card>
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-display-xs font-semibold text-ink">Ledger</h2>
          <div className="flex items-center gap-2">
            <select
              className="h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="issued">Issued</option>
              <option value="partially_paid">Partially paid</option>
              <option value="paid">Paid</option>
              <option value="overdue">Overdue</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <Button variant="outline" onClick={() => downloadFile('/invoices/export.csv', 'invoices.csv')}>
              Export CSV
            </Button>
            <Button asChild>
              <Link to="/invoices/new">New invoice</Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Number</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Tax</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead></TableHead>
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
                  <TableCell>
                    {inv.tax_treatment_snapshot && <TaxTreatmentBadge treatment={inv.tax_treatment_snapshot} />}
                  </TableCell>
                  <TableCell className="text-right">
                    {inv.currency} {inv.total}
                  </TableCell>
                  <TableCell>
                    {inv.status !== 'draft' && (
                      <Button variant="outline" size="sm" onClick={() => downloadFile(`/invoices/${inv.id}/pdf`, `${inv.number}.pdf`)}>
                        PDF
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {invoices.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-6 text-center text-body-sm text-mute">
                    No invoices yet. Add a client, then bill them -- most people are done in about two minutes.
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
