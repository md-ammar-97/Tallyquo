import { useState } from 'react'
import { api, ApiError, downloadFile } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

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

  const selectClass = 'h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm'

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">Reports</h1>

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Profit &amp; loss</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-body-sm font-medium text-mute">P&amp;L grouped by</label>
            <select className={selectClass} value={pnlGroupBy} onChange={(e) => setPnlGroupBy(e.target.value)}>
              <option value="month">Month</option>
              <option value="quarter">Quarter</option>
              <option value="year">Year</option>
            </select>
          </div>
          <Button variant="outline" onClick={() => downloadFile(`/reports/pnl.csv?group_by=${pnlGroupBy}`, 'pnl.csv')}>
            Download P&amp;L CSV
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Year-end accountant pack</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-body-sm font-medium text-mute">Year</label>
              <select className={selectClass} value={packYear} onChange={(e) => setPackYear(e.target.value)}>
                {yearOptions.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>
            <Button onClick={handleGeneratePack} disabled={packGenerating}>
              {packGenerating ? 'Generating…' : 'Generate pack'}
            </Button>
            {packResult && (
              <a
                className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
                href={packResult.url}
                target="_blank"
                rel="noreferrer"
              >
                Download {packResult.filename} ({(packResult.byte_size / 1024).toFixed(0)} KB)
              </a>
            )}
          </div>
          {packError && <p className="text-body-sm text-negative">{packError}</p>}
          {packResult && (
            <p className="text-body-sm text-mute">
              Invoice PDFs, expenses (T2125-mapped), receipt images, GST/HST quarterly summary, and P&amp;L, zipped.
              This link works for 7 days from generation -- not tax advice, a record of what's in Tallyquo.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
