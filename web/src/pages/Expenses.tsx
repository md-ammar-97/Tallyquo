import { useEffect, useRef, useState } from 'react'
import { api, ApiError, API_BASE_URL, downloadFile } from '../api'
import { todayLocal } from '../dateUtils'

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
  const [categories, setCategories] = useState<Category[]>([])
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [form, setForm] = useState(emptyForm)
  const [receiptId, setReceiptId] = useState<string | null>(null)
  const [ocr, setOcr] = useState<OcrResult | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [showManual, setShowManual] = useState(false)
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
    <div>
      <h1>Expenses</h1>

      {!showConfirm && !showManual && (
        <div
          className="block"
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
          <div
            className="block-body"
            style={{
              textAlign: 'center',
              padding: 48,
              border: dragOver ? '2px dashed var(--color-accent-default)' : '2px dashed var(--color-border-strong)',
              borderRadius: 'var(--radius-md)',
              margin: 16,
              cursor: 'pointer',
            }}
            onClick={() => fileInput.current?.click()}
          >
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/gif,application/pdf"
              style={{ display: 'none' }}
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            />
            <input
              ref={cameraInput}
              type="file"
              accept="image/*"
              capture="environment"
              style={{ display: 'none' }}
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            />
            <p style={{ fontWeight: 600, marginBottom: 4 }}>{uploading ? 'Uploading…' : '⇪ Drop a receipt'}</p>
            <p className="caption">
              or{' '}
              <a
                href="#"
                style={{ color: 'var(--color-text-link)' }}
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
                style={{ color: 'var(--color-text-link)' }}
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
          {error && (
            <p className="error-text" style={{ padding: '0 16px 16px' }}>
              {error}
            </p>
          )}
        </div>
      )}

      {(showConfirm || showManual) && (
        <div className="block">
          <div className="block-header">
            <h2>{showConfirm ? 'Confirm receipt details' : 'New expense'}</h2>
          </div>
          <div className="block-body">
            <form onSubmit={handleSave}>
              <div className="field-row">
                <div className="field">
                  <label>Vendor</label>
                  <input value={form.vendor} onChange={(e) => setForm({ ...form, vendor: e.target.value })} />
                </div>
                <div className="field">
                  <label>Date</label>
                  <input
                    type="date"
                    required
                    value={form.expense_date}
                    onChange={(e) => setForm({ ...form, expense_date: e.target.value })}
                  />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Amount (total paid)</label>
                  <input
                    required
                    value={form.amount_total}
                    onChange={(e) => setForm({ ...form, amount_total: e.target.value })}
                    placeholder="0.00"
                    style={
                      showConfirm && lowConfidence
                        ? { borderColor: 'var(--color-status-attention)', background: 'var(--color-status-attention-bg)' }
                        : undefined
                    }
                  />
                </div>
                <div className="field">
                  <label>Tax amount</label>
                  <input
                    value={form.tax_amount}
                    onChange={(e) => setForm({ ...form, tax_amount: e.target.value })}
                    placeholder="0.00"
                  />
                </div>
              </div>
              <div className="field">
                <label>Category</label>
                <select
                  value={form.category_id}
                  onChange={(e) => setForm({ ...form, category_id: e.target.value })}
                >
                  <option value="">Uncategorized</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                      {Number(c.deductible_pct) < 100 ? ` (${c.deductible_pct}% deductible)` : ''}
                    </option>
                  ))}
                </select>
              </div>
              {error && <p className="error-text">{error}</p>}
              <button type="submit" className="primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save expense'}
              </button>{' '}
              <button
                type="button"
                onClick={() => {
                  setShowConfirm(false)
                  setShowManual(false)
                  setForm(emptyForm)
                  setReceiptId(null)
                  setOcr(null)
                }}
              >
                Cancel
              </button>
            </form>
          </div>
        </div>
      )}

      <div className="block">
        <div className="block-header">
          <h2>All expenses</h2>
          <button onClick={() => downloadFile('/expenses/export.csv', 'expenses.csv')}>Export CSV</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Vendor</th>
              <th>Category</th>
              <th className="amount">Amount</th>
              <th>ITC</th>
            </tr>
          </thead>
          <tbody>
            {expenses.map((exp) => (
              <tr key={exp.id}>
                <td>{exp.expense_date}</td>
                <td>{exp.vendor ?? '—'}</td>
                <td>{exp.category_name ?? '—'}</td>
                <td className="amount">CAD {exp.amount_total}</td>
                <td>{exp.itc_eligible ? <span className="badge taxable">ITC</span> : ''}</td>
              </tr>
            ))}
            {expenses.length === 0 && (
              <tr>
                <td colSpan={5} className="caption" style={{ padding: 24 }}>
                  No expenses logged yet. Drop a receipt above, or enter one manually.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
