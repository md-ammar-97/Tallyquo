import { useState } from 'react'
import { api, ApiError, downloadFile } from '../api'

export default function Reports() {
  const [pnlGroupBy, setPnlGroupBy] = useState('month')

  const currentYear = new Date().getFullYear()
  const yearOptions = [currentYear, currentYear - 1, currentYear - 2]
  const [packYear, setPackYear] = useState(String(currentYear - 1))
  const [packGenerating, setPackGenerating] = useState(false)
  const [packResult, setPackResult] = useState<{ url: string; filename: string; byte_size: number } | null>(null)
  const [packError, setPackError] = useState<string | null>(null)

  async function handleGeneratePack() {
    setPackGenerating(true)
    setPackError(null)
    setPackResult(null)
    try {
      const result = await api.post<{ url: string; filename: string; byte_size: number }>(
        `/exports/year-end?year=${packYear}`
      )
      setPackResult(result)
    } catch (err) {
      setPackError(err instanceof ApiError ? err.message : 'Could not generate the year-end pack.')
    } finally {
      setPackGenerating(false)
    }
  }

  return (
    <div>
      <h1>Reports</h1>

      <div className="block">
        <div className="block-header">
          <h2>Profit &amp; loss</h2>
        </div>
        <div className="block-body" style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>P&amp;L grouped by</label>
            <select value={pnlGroupBy} onChange={(e) => setPnlGroupBy(e.target.value)}>
              <option value="month">Month</option>
              <option value="quarter">Quarter</option>
              <option value="year">Year</option>
            </select>
          </div>
          <button onClick={() => downloadFile(`/reports/pnl.csv?group_by=${pnlGroupBy}`, 'pnl.csv')}>
            Download P&amp;L CSV
          </button>
        </div>
      </div>

      <div className="block">
        <div className="block-header">
          <h2>Year-end accountant pack</h2>
        </div>
        <div className="block-body" style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Year</label>
            <select value={packYear} onChange={(e) => setPackYear(e.target.value)}>
              {yearOptions.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>
          <button onClick={handleGeneratePack} disabled={packGenerating}>
            {packGenerating ? 'Generating…' : 'Generate pack'}
          </button>
          {packResult && (
            <a href={packResult.url} target="_blank" rel="noreferrer">
              Download {packResult.filename} ({(packResult.byte_size / 1024).toFixed(0)} KB)
            </a>
          )}
        </div>
        {packError && (
          <div className="block-body" style={{ paddingTop: 0 }}>
            <p className="error-text">{packError}</p>
          </div>
        )}
        {packResult && (
          <div className="block-body" style={{ paddingTop: 0 }}>
            <p className="caption">
              Invoice PDFs, expenses (T2125-mapped), receipt images, GST/HST quarterly summary, and P&amp;L, zipped.
              This link works for 7 days from generation -- not tax advice, a record of what's in Tallyquo.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
