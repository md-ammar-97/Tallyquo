import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { API_BASE_URL } from '../api'
import InvoiceDocument, { type InvoiceDocumentData } from '../components/InvoiceDocument'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { InvoiceStatusBadge, TaxTreatmentBadge } from '../components/InvoiceBadges'

interface Invoice {
  id: string
  number: string | null
  status: string
  invoice_date: string | null
  due_date: string | null
  currency: string
  total: string
  amount_paid: string
  tax_treatment_snapshot: string | null
}

export default function PublicInvoice() {
  const { token } = useParams<{ token: string }>()
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [doc, setDoc] = useState<InvoiceDocumentData | null>(null)
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
    fetch(`${API_BASE_URL}/public/invoices/${token}/document`)
      .then((res) => {
        if (!res.ok) throw new Error('not found')
        return res.json()
      })
      .then(setDoc)
      .catch(() => {})
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
      <main className="flex min-h-screen items-center justify-center bg-background">
        <Card className="w-[400px]">
          <CardContent>
            <p className="text-body-sm text-mute">This link is no longer valid, or the invoice doesn't exist.</p>
          </CardContent>
        </Card>
      </main>
    )
  }
  if (!invoice) return null

  return (
    <main className="flex min-h-screen justify-center bg-background px-4 py-12">
      <div className="w-full max-w-[720px]">
        <h1 className="mb-4 font-display text-display-sm text-ink">{invoice.number}</h1>
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
            <Button onClick={handleDownload} className="self-start">
              Download PDF
            </Button>
            {doc && <InvoiceDocument data={doc} />}
          </CardContent>
        </Card>
      </div>
    </main>
  )
}
