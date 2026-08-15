import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

interface Client {
  id: string
  legal_name: string
  country_code: string
  region_code: string | null
  tax_treatment: string
  outstanding_cad: string
  has_overdue: boolean
}

interface ClientSummaryPage {
  items: Client[]
  total: number
}

const emptyForm = {
  legal_name: '',
  country_code: 'CA',
  region_code: '',
  tax_treatment: 'taxable',
  address_line1: '',
  city: '',
}

const PAGE_SIZE = 20

// Display-only: the client-level GST/HST registration status a tax
// treatment badge shows. Real tax computation always happens
// server-side per invoice (tax/engine.py) -- this never feeds a
// calculation, only labels what a client's default is. PST/QST are
// deliberately not shown here: they're an invoice-level opt-in
// (include_provincial_sales_tax), not a stored client default, so a
// compound "GST + PST" label would imply data this record doesn't have.
const HST_PROVINCES: Record<string, number> = { ON: 13, NS: 14, NB: 15, NL: 15, PE: 15 }
const GST_RATE = 5

function taxLabel(c: Client): string {
  if (c.tax_treatment === 'zero_rated_export') return 'Zero-rated export'
  if (c.tax_treatment === 'not_registered') return 'Not registered'
  if (c.tax_treatment === 'exempt') return 'Exempt'
  const rate = c.region_code ? HST_PROVINCES[c.region_code] : undefined
  if (rate) return `${c.region_code} — ${rate}% HST`
  return c.region_code ? `${c.region_code} — ${GST_RATE}% GST` : `${GST_RATE}% GST`
}

function formatMoney(amount: string): string {
  return `CAD ${Number(amount).toLocaleString('en-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export default function Clients() {
  const [clients, setClients] = useState<Client[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [form, setForm] = useState(emptyForm)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function load() {
    api
      .get<ClientSummaryPage>(`/clients/summary?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`)
      .then((data) => {
        setClients(data.items)
        setTotal(data.total)
      })
  }

  useEffect(load, [page])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const body: Record<string, unknown> = {
        ...form,
        address_line1: form.address_line1 || null,
        city: form.city || null,
      }
      if (form.country_code !== 'CA') {
        body.tax_treatment = 'zero_rated_export'
        delete body.region_code
      }
      await api.post('/clients', body)
      setForm(emptyForm)
      setShowForm(false)
      setPage(0)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create client.')
    } finally {
      setSaving(false)
    }
  }

  const from = total === 0 ? 0 : page * PAGE_SIZE + 1
  const to = Math.min(total, (page + 1) * PAGE_SIZE)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-display-sm text-ink">Clients</h1>
          <p className="text-body-sm text-mute">Manage your active clients, jurisdictions, and standard tax treatments.</p>
        </div>
        <Button onClick={() => setShowForm((s) => !s)}>{showForm ? 'Cancel' : '+ Add Client'}</Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-display-xs font-semibold text-ink">Add client</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label>Legal name</Label>
                <Input required value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} />
              </div>
              <div className="flex flex-wrap gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label>Country</Label>
                  <select
                    className="h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm"
                    value={form.country_code}
                    onChange={(e) => setForm({ ...form, country_code: e.target.value })}
                  >
                    <option value="CA">Canada</option>
                    <option value="US">United States</option>
                  </select>
                </div>
                {form.country_code === 'CA' && (
                  <div className="flex flex-col gap-1.5">
                    <Label>Province</Label>
                    <Input
                      required
                      placeholder="ON"
                      value={form.region_code}
                      onChange={(e) => setForm({ ...form, region_code: e.target.value.toUpperCase() })}
                    />
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label>Address (optional)</Label>
                  <Input value={form.address_line1} onChange={(e) => setForm({ ...form, address_line1: e.target.value })} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>City (optional)</Label>
                  <Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
                </div>
              </div>
              <p className="text-body-sm text-mute">
                {form.country_code === 'CA'
                  ? 'Tax rate is derived from this province, not your own location.'
                  : 'Non-resident clients are zero-rated exports by default -- 0% tax, but still counts toward your $30,000 registration threshold.'}
              </p>
              {error && <p className="text-body-sm text-negative">{error}</p>}
              <Button type="submit" disabled={saving} className="self-start">
                {saving ? 'Saving…' : 'Add client'}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="font-display text-display-xs font-semibold text-ink">All clients</CardTitle>
          <Button variant="outline" onClick={() => downloadFile('/clients/export.csv', 'clients.csv')}>Export CSV</Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Legal name</TableHead>
                <TableHead>Jurisdiction</TableHead>
                <TableHead>Default tax treatment</TableHead>
                <TableHead className="text-right">Outstanding</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {clients.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>
                    <Link className="text-ink underline underline-offset-2 hover:text-mute" to={`/clients/${c.id}`}>
                      {c.legal_name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {c.region_code ? `${c.region_code}, ` : ''}
                    {c.country_code}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{taxLabel(c)}</Badge>
                  </TableCell>
                  <TableCell className={`text-right font-mono ${c.has_overdue ? 'text-negative' : ''}`}>
                    {formatMoney(c.outstanding_cad)}
                  </TableCell>
                  <TableCell>
                    <Link className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute" to={`/clients/${c.id}`}>
                      View
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
              {clients.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-6 text-center text-body-sm text-mute">
                    No clients yet. Add the people you bill -- we'll work out the right tax treatment for each one.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          {total > 0 && (
            <div className="mt-3 flex items-center justify-between">
              <span className="text-body-sm text-mute">
                Showing {from}-{to} of {total} clients
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                  ← Previous
                </Button>
                <Button variant="outline" size="sm" disabled={to >= total} onClick={() => setPage((p) => p + 1)}>
                  Next →
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
