import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'
import { todayLocal } from '../dateUtils'
import InvoiceDocument, { type InvoiceDocumentData } from '../components/InvoiceDocument'
import ComplianceChecklist, { type ComplianceProfile } from '../components/ComplianceChecklist'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'

const selectClass = 'h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm'
const fieldCol = 'flex flex-1 flex-col gap-1.5'

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
      <div className="flex flex-col gap-6">
        <h1 className="font-display text-display-sm text-ink">Invoice issued</h1>
        <Card>
          <CardContent className="flex flex-col gap-3">
            <Badge variant="secondary" className="w-fit">Issued</Badge>
            <h2 className="font-display text-display-xs font-semibold text-ink">{issuedInvoice.number}</h2>
            <p className="text-body-sm text-mute">
              Total: {currency} {issuedInvoice.total}
            </p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => downloadFile(`/invoices/${issuedInvoice.id}/pdf`, `${issuedInvoice.number}.pdf`)}>
                Download PDF
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setIssuedInvoice(null)
                  setLines([emptyLine()])
                }}
              >
                Create another
              </Button>
              <Button variant="outline" onClick={() => navigate('/invoices')}>View ledger</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const selectedClient = clients.find((c) => c.id === clientId) || null

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">New invoice</h1>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,480px)]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-display-xs font-semibold text-ink">Invoice details</CardTitle>
            </CardHeader>
            <CardContent>
              {clients.length === 0 ? (
                <p className="text-body-sm text-mute">
                  No clients yet.{' '}
                  <a href="/clients" className="font-medium text-ink underline underline-offset-2 hover:text-mute">
                    Add a client
                  </a>{' '}
                  first.
                </p>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className={fieldCol}>
                    <Label>Client</Label>
                    <select className={selectClass} value={clientId} onChange={(e) => setClientId(e.target.value)}>
                      {clients.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.legal_name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-wrap gap-4">
                    <div className={fieldCol}>
                      <Label>Issue date</Label>
                      <Input type="date" value={invoiceDate} onChange={(e) => handleInvoiceDateChange(e.target.value)} />
                    </div>
                    <div className={fieldCol}>
                      <Label>Due date</Label>
                      <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-4">
                    <div className={fieldCol}>
                      <Label>Terms</Label>
                      <select className={selectClass} value={termsDays} onChange={(e) => handleTermsChange(Number(e.target.value))}>
                        {TERMS_OPTIONS.map((t) => (
                          <option key={t.days} value={t.days}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className={fieldCol}>
                      <Label>Currency</Label>
                      <select className={selectClass} value={currency} onChange={(e) => setCurrency(e.target.value)}>
                        <option value="CAD">CAD</option>
                        <option value="USD">USD</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-4">
                    <div className={fieldCol}>
                      <Label>Service period start (optional)</Label>
                      <Input type="date" value={servicePeriodStart} onChange={(e) => setServicePeriodStart(e.target.value)} />
                    </div>
                    <div className={fieldCol}>
                      <Label>Service period end (optional)</Label>
                      <Input type="date" value={servicePeriodEnd} onChange={(e) => setServicePeriodEnd(e.target.value)} />
                    </div>
                  </div>
                  <div className={fieldCol}>
                    <Label>PO reference (optional)</Label>
                    <Input value={poReference} onChange={(e) => setPoReference(e.target.value)} />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-display text-display-xs font-semibold text-ink">Line items</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {lines.map((line, i) => (
                <div key={i} className="flex items-end gap-2">
                  <div className="flex flex-[3] flex-col gap-1.5">
                    {i === 0 && <Label>Description</Label>}
                    <Input
                      value={line.description}
                      onChange={(e) => updateLine(i, { description: e.target.value })}
                      placeholder="Consulting services"
                    />
                  </div>
                  <div className="flex flex-1 flex-col gap-1.5">
                    {i === 0 && <Label>Qty</Label>}
                    <Input value={line.quantity} onChange={(e) => updateLine(i, { quantity: e.target.value })} />
                  </div>
                  <div className="flex flex-1 flex-col gap-1.5">
                    {i === 0 && <Label>Amount</Label>}
                    <Input
                      value={line.amount}
                      onChange={(e) => updateLine(i, { amount: e.target.value, unit_rate: e.target.value })}
                      placeholder="0.00"
                    />
                  </div>
                  <button
                    className="h-9 shrink-0 px-2 text-body-sm text-mute hover:text-ink"
                    onClick={() => removeLine(i)}
                    disabled={lines.length === 1}
                  >
                    &times;
                  </button>
                </div>
              ))}
              <button
                className="self-start text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
                onClick={addLine}
              >
                + Add line
              </button>
            </CardContent>
          </Card>

          <div className="flex flex-col gap-1.5">
            <Label>Notes (optional, shown on invoice)</Label>
            <textarea
              rows={3}
              className="rounded-md border border-ink bg-canvas px-3 py-2 text-body-sm"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {previewError && (
            <Card className="border-l-4 border-l-negative">
              <CardContent className="text-body-sm text-negative">{previewError}</CardContent>
            </Card>
          )}
          {preview?.warnings.map((w, i) => (
            <Card key={i} className="border-l-4 border-l-warning">
              <CardContent className="text-body-sm text-warning-content">{w}</CardContent>
            </Card>
          ))}

          <ComplianceChecklist
            profile={profile}
            client={selectedClient}
            taxReady={!!preview && !previewError}
          />

          {issueError && <p className="text-body-sm text-negative">{issueError}</p>}
          <Button
            onClick={handleIssue}
            disabled={issuing || !preview || clients.length === 0}
            className="h-10 self-start px-6"
          >
            {issuing ? 'Issuing…' : 'Issue invoice'}
          </Button>
        </div>

        <Card className="lg:sticky lg:top-4 lg:max-h-[calc(100vh-96px)] lg:overflow-y-auto">
          <CardHeader>
            <CardTitle className="font-display text-display-xs font-semibold text-ink">Preview</CardTitle>
          </CardHeader>
          <CardContent>
            {preview ? (
              <InvoiceDocument data={preview} />
            ) : (
              <p className="text-body-sm text-mute">Add a client and a line item to see the invoice preview.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
