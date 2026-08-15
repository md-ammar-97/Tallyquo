import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, ApiError, API_BASE_URL, downloadFile } from '../api'
import { todayLocal } from '../dateUtils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const selectClass = 'h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm'
const fieldCol = 'flex flex-1 flex-col gap-1.5'

interface Category {
  id: string
  name: string
  t2125_line: string | null
  deductible_pct: string
  is_capital: boolean
}

interface Expense {
  id: string
  expense_date: string
  vendor: string | null
  category_id: string | null
  category_name: string | null
  amount_total: string
  tax_amount: string
  business_use_pct: string
  itc_eligible: boolean
  is_rebilled: boolean
  source: string
}

interface OcrResult {
  vendor: string | null
  date: string | null
  amount: string | null
  confidence: number | null
}

const emptyForm = {
  expense_date: todayLocal(),
  vendor: '',
  category_id: '',
  amount_total: '',
  tax_amount: '0',
  business_use_pct: '100',
}

export default function Expenses() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [categories, setCategories] = useState<Category[]>([])
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [form, setForm] = useState(emptyForm)
  const [receiptId, setReceiptId] = useState<string | null>(null)
  const [ocr, setOcr] = useState<OcrResult | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [showManual, setShowManual] = useState(searchParams.get('new') === '1')
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const cameraInput = useRef<HTMLInputElement>(null)

  function load() {
    api.get<Category[]>('/expenses/categories').then(setCategories)
    api.get<Expense[]>('/expenses').then(setExpenses)
  }

  useEffect(load, [])

  useEffect(() => {
    if (searchParams.get('new') === '1') setSearchParams({}, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleFile(file: File) {
    setUploading(true)
    setError(null)
    try {
      const body = new FormData()
      body.append('file', file)
      const headers: Record<string, string> = {}
      const token = localStorage.getItem('access_token')
      if (token) headers.Authorization = `Bearer ${token}`
      const res = await fetch(`${API_BASE_URL}/expenses/receipts`, { method: 'POST', headers, body })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new ApiError(res.status, detail.detail ?? 'Could not upload receipt.')
      }
      const data = await res.json()
      setReceiptId(data.id)
      if (data.already_existed) {
        setError('This receipt was already uploaded.')
        setShowConfirm(false)
        setShowManual(true)
        return
      }
      setOcr(data.ocr)
      setForm({
        ...emptyForm,
        vendor: data.ocr?.vendor ?? '',
        expense_date: data.ocr?.date ?? emptyForm.expense_date,
        amount_total: data.ocr?.amount ?? '',
      })
      setShowConfirm(true)
      setShowManual(false)
    } catch (err) {
      // E3: OCR/upload trouble falls straight to manual entry, no error dialog.
      setShowManual(true)
      setShowConfirm(false)
      if (err instanceof ApiError && err.status !== 503) setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.post('/expenses', {
        ...form,
        category_id: form.category_id || null,
        receipt_id: receiptId,
      })
      setForm(emptyForm)
      setReceiptId(null)
      setOcr(null)
      setShowConfirm(false)
      setShowManual(false)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save expense.')
    } finally {
      setSaving(false)
    }
  }

  const lowConfidence = ocr?.confidence !== null && ocr?.confidence !== undefined && ocr.confidence < 0.6

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">Expenses</h1>

      {!showConfirm && !showManual && (
        <Card
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0])
          }}
        >
          <CardContent className="flex flex-col gap-2">
            <div
              className={`cursor-pointer rounded-md border-2 border-dashed p-12 text-center ${dragOver ? 'border-ink' : 'border-divider'}`}
              onClick={() => fileInput.current?.click()}
            >
              <input
                ref={fileInput}
                type="file"
                accept="image/png,image/jpeg,image/gif,application/pdf"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
              <input
                ref={cameraInput}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
              <p className="mb-1 text-body-sm font-semibold text-ink">{uploading ? 'Uploading…' : '⇪ Drop a receipt'}</p>
              <p className="text-body-sm text-mute">
                or{' '}
                <a
                  href="#"
                  className="font-medium text-ink underline underline-offset-2 hover:text-mute"
                  onClick={(e) => {
                    e.stopPropagation()
                    e.preventDefault()
                    cameraInput.current?.click()
                  }}
                >
                  take a photo
                </a>{' '}
                ·{' '}
                <a
                  href="#"
                  className="font-medium text-ink underline underline-offset-2 hover:text-mute"
                  onClick={(e) => {
                    e.stopPropagation()
                    e.preventDefault()
                    setShowManual(true)
                  }}
                >
                  enter manually
                </a>
              </p>
            </div>
            {error && <p className="text-body-sm text-negative">{error}</p>}
          </CardContent>
        </Card>
      )}

      {(showConfirm || showManual) && (
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-display-xs font-semibold text-ink">
              {showConfirm ? 'Confirm receipt details' : 'New expense'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSave} className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-4">
                <div className={fieldCol}>
                  <Label>Vendor</Label>
                  <Input value={form.vendor} onChange={(e) => setForm({ ...form, vendor: e.target.value })} />
                </div>
                <div className={fieldCol}>
                  <Label>Date</Label>
                  <Input
                    type="date"
                    required
                    value={form.expense_date}
                    onChange={(e) => setForm({ ...form, expense_date: e.target.value })}
                  />
                </div>
              </div>
              <div className="flex flex-wrap gap-4">
                <div className={fieldCol}>
                  <Label>Amount (total paid)</Label>
                  <Input
                    required
                    value={form.amount_total}
                    onChange={(e) => setForm({ ...form, amount_total: e.target.value })}
                    placeholder="0.00"
                    className={showConfirm && lowConfidence ? 'border-warning-deep bg-warning/10' : undefined}
                  />
                </div>
                <div className={fieldCol}>
                  <Label>Tax amount</Label>
                  <Input value={form.tax_amount} onChange={(e) => setForm({ ...form, tax_amount: e.target.value })} placeholder="0.00" />
                </div>
              </div>
              <div className={fieldCol}>
                <Label>Category</Label>
                <select className={selectClass} value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
                  <option value="">Uncategorized</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                      {Number(c.deductible_pct) < 100 ? ` (${c.deductible_pct}% deductible)` : ''}
                    </option>
                  ))}
                </select>
              </div>
              {error && <p className="text-body-sm text-negative">{error}</p>}
              <div className="flex gap-3">
                <Button type="submit" disabled={saving}>
                  {saving ? 'Saving…' : 'Save expense'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowConfirm(false)
                    setShowManual(false)
                    setForm(emptyForm)
                    setReceiptId(null)
                    setOcr(null)
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="font-display text-display-xs font-semibold text-ink">All expenses</CardTitle>
          <Button variant="outline" onClick={() => downloadFile('/expenses/export.csv', 'expenses.csv')}>Export CSV</Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Vendor</TableHead>
                <TableHead>Category</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>ITC</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {expenses.map((exp) => (
                <TableRow key={exp.id}>
                  <TableCell>{exp.expense_date}</TableCell>
                  <TableCell>{exp.vendor ?? '—'}</TableCell>
                  <TableCell>{exp.category_name ?? '—'}</TableCell>
                  <TableCell className="text-right">CAD {exp.amount_total}</TableCell>
                  <TableCell>{exp.itc_eligible ? <Badge variant="secondary">ITC</Badge> : ''}</TableCell>
                </TableRow>
              ))}
              {expenses.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-6 text-center text-body-sm text-mute">
                    No expenses logged yet. Drop a receipt above, or enter one manually.
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
