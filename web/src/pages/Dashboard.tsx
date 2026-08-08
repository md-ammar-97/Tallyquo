import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'

interface TaxBand {
  income_from: string
  income_to: string | null
  rate: string
  taxable_amount: string
  tax: string
}

interface MarginalTax {
  jurisdiction: string
  net_income: string
  bands: TaxBand[]
  total_tax: string
}

interface SetAside {
  net_business_income: string
  federal_tax: MarginalTax
  provincial_tax: MarginalTax
  cpp: {
    pensionable_earnings: string
    base_contribution: string
    cpp2_pensionable_earnings: string
    cpp2_contribution: string
    total_contribution: string
  }
  total_estimated_tax_and_cpp: string
  recommended_set_aside_pct: string
}

interface IncomeView {
  mode: 'derived' | 'declared'
  derived: {
    extrapolated_annual_income: string
    scheduled_recurring_income: string
    projected_annual_income: string
    is_low_confidence: boolean
    method: string
  }
  declared_annual_income: string | null
  active_projected_income: string
  variance_from_derived: string | null
}

interface Threshold {
  rolling_revenue: string
  threshold: string
  pct_of_threshold: string
  window_start: string
  window_end: string
  escalation: 'ok' | 'attention' | 'overdue'
}

interface InstalmentWarning {
  applies: boolean
  projected_net_tax_owing: string
  threshold: string
}

interface Projection {
  year: number
  as_of: string
  jurisdiction: string
  income: IncomeView
  set_aside: SetAside
  quarterly_net_owing: { period: string; collected: string; itcs_claimable: string; net_owing: string }[]
  threshold: Threshold
  instalment_warning: InstalmentWarning
}

function formatDisplay(amount: string): string {
  const n = Number(amount)
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

export default function Dashboard() {
  const [pnlGroupBy, setPnlGroupBy] = useState('month')
  const [projection, setProjection] = useState<Projection | null>(null)
  const [projectionError, setProjectionError] = useState<string | null>(null)
  const [assumptionsOpen, setAssumptionsOpen] = useState(false)
  const [declaredDraft, setDeclaredDraft] = useState('')
  const [editingDeclared, setEditingDeclared] = useState(false)

  async function loadProjection(year?: number) {
    try {
      const data = await api.get<Projection>(`/projection${year ? `?year=${year}` : ''}`)
      setProjection(data)
      setProjectionError(null)
    } catch (err) {
      setProjection(null)
      setProjectionError(err instanceof ApiError ? err.message : 'Could not load projection.')
    }
  }

  useEffect(() => {
    loadProjection()
  }, [])

  async function handleSaveDeclared(e: React.FormEvent) {
    e.preventDefault()
    if (!projection) return
    await api.put('/projection/declared-income', {
      year: projection.year,
      declared_annual_income: declaredDraft,
    })
    setEditingDeclared(false)
    await loadProjection(projection.year)
  }

  async function handleClearDeclared() {
    if (!projection) return
    await api.delete(`/projection/declared-income/${projection.year}`)
    await loadProjection(projection.year)
  }

  function changeYear(delta: number) {
    if (!projection) return
    loadProjection(projection.year + delta)
  }

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="block">
        <div className="block-body">
          <p style={{ marginBottom: 16 }}>
            Set up your business profile and a client, then issue a correctly-taxed invoice in under two minutes.
          </p>
          <Link to="/profile">
            <button>1. Business profile</button>
          </Link>{' '}
          <Link to="/clients">
            <button>2. Add a client</button>
          </Link>{' '}
          <Link to="/invoices/new">
            <button className="primary">3. Issue an invoice</button>
          </Link>
        </div>
      </div>

      {projectionError && (
        <div className="block">
          <div className="block-body">
            <p className="caption">{projectionError}</p>
          </div>
        </div>
      )}

      {projection && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span className="caption">Projection for {projection.year}</span>
            <span>
              <button className="link-button" onClick={() => changeYear(-1)}>&larr; {projection.year - 1}</button>{' '}
              <button className="link-button" onClick={() => changeYear(1)}>{projection.year + 1} &rarr;</button>
            </span>
          </div>

          <div className="metric-grid">
            <div className={`metric-tile${assumptionsOpen ? ' expanded' : ''}`}>
              <div className="metric-label">Set aside for tax</div>
              <div className="metric-value display">{formatDisplay(projection.set_aside.total_estimated_tax_and_cpp)}</div>
              <p className="caption metric-sub">
                {projection.income.mode === 'declared' ? 'based on declared income' : 'estimate'}
                {projection.income.derived.is_low_confidence && projection.income.mode === 'derived' && ' -- low confidence, early in the year'}
              </p>
              <button className="assumptions-toggle" onClick={() => setAssumptionsOpen((o) => !o)}>
                {assumptionsOpen ? 'Hide assumptions' : 'Show assumptions'}
              </button>
              {assumptionsOpen && (
                <div className="assumptions-list">
                  <div className="row">
                    <span className="label">Net business income</span>
                    <span>CAD {projection.set_aside.net_business_income}</span>
                  </div>
                  <div className="row">
                    <span className="label">Federal income tax (est.)</span>
                    <span>CAD {projection.set_aside.federal_tax.total_tax}</span>
                  </div>
                  <div className="row">
                    <span className="label">{projection.jurisdiction} income tax (est.)</span>
                    <span>CAD {projection.set_aside.provincial_tax.total_tax}</span>
                  </div>
                  <div className="row">
                    <span className="label">CPP (self-employed, both halves)</span>
                    <span>CAD {projection.set_aside.cpp.total_contribution}</span>
                  </div>
                  <div className="row">
                    <span className="label">Recommended set-aside</span>
                    <span>{projection.set_aside.recommended_set_aside_pct}% of net income</span>
                  </div>
                  <p className="caption" style={{ marginTop: 4 }}>
                    Estimate only, not tax advice. Based on {projection.income.mode === 'declared' ? 'your declared annual income' : `${projection.income.derived.method.replace(/_/g, ' ')}`} of CAD {projection.income.active_projected_income}, accrual basis (by invoice and expense date, not when cash actually changed hands).
                  </p>

                  {projection.income.mode === 'declared' ? (
                    <p className="caption">
                      Derived (extrapolated) estimate: CAD {projection.income.derived.projected_annual_income}
                      {projection.income.variance_from_derived && ` (gap: CAD ${projection.income.variance_from_derived})`}{' '}
                      <button className="link-button" onClick={handleClearDeclared}>Use derived instead</button>
                    </p>
                  ) : editingDeclared ? (
                    <form onSubmit={handleSaveDeclared} style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
                      <input
                        type="number"
                        step="0.01"
                        placeholder="Declared annual income"
                        value={declaredDraft}
                        onChange={(e) => setDeclaredDraft(e.target.value)}
                        style={{ width: 160 }}
                        required
                      />
                      <button type="submit">Save</button>
                      <button type="button" className="link-button" onClick={() => setEditingDeclared(false)}>Cancel</button>
                    </form>
                  ) : (
                    <button className="link-button" onClick={() => setEditingDeclared(true)}>
                      Declare your own income figure instead
                    </button>
                  )}
                </div>
              )}
            </div>

            <div className="metric-tile">
              <div className="metric-label">Threshold tracker</div>
              <div className="metric-value">{projection.threshold.pct_of_threshold}%</div>
              <div className={`progress-bar`}>
                <div
                  className={`progress-bar-fill ${projection.threshold.escalation !== 'ok' ? projection.threshold.escalation : ''}`}
                  style={{ width: `${Math.min(100, Number(projection.threshold.pct_of_threshold))}%` }}
                />
              </div>
              <p className="caption metric-sub">
                {(Number(projection.threshold.threshold) - Number(projection.threshold.rolling_revenue)) > 0
                  ? `CAD ${(Number(projection.threshold.threshold) - Number(projection.threshold.rolling_revenue)).toFixed(2)} from the CAD ${projection.threshold.threshold} registration threshold. Crossing it changes what you must charge.`
                  : 'Threshold reached -- registration is required.'}
              </p>
              <p className="caption" style={{ marginTop: 4 }}>
                Based on this account only -- the $30,000 threshold is shared across any associated businesses you also run.
              </p>
            </div>

            <div className="metric-tile">
              <div className="metric-label">GST/HST held for CRA (this year)</div>
              <div className="metric-value display">
                CAD {projection.quarterly_net_owing.reduce((sum, q) => sum + Number(q.net_owing), 0).toFixed(2)}
              </div>
              <p className="caption metric-sub">collected minus input tax credits, by quarter -- never revenue</p>
            </div>

            {projection.instalment_warning.applies && (
              <div className="metric-tile" style={{ borderLeft: '3px solid var(--color-status-attention)' }}>
                <div className="metric-label">Instalment reminder</div>
                <p className="caption">
                  Projected net income tax + CPP owing (CAD {projection.instalment_warning.projected_net_tax_owing}) is over
                  CAD {projection.instalment_warning.threshold} -- the CRA may expect quarterly instalments. Confirm with your accountant.
                </p>
              </div>
            )}
          </div>

          <div className="block">
            <div className="block-header">
              <h2>GST/HST net-owing by quarter</h2>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Quarter</th>
                  <th>Collected</th>
                  <th>ITCs claimable</th>
                  <th>Net owing</th>
                </tr>
              </thead>
              <tbody>
                {projection.quarterly_net_owing.map((q) => (
                  <tr key={q.period}>
                    <td>{q.period}</td>
                    <td>CAD {q.collected}</td>
                    <td>CAD {q.itcs_claimable}</td>
                    <td>CAD {q.net_owing}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="block">
        <div className="block-header">
          <h2>Reports</h2>
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
    </div>
  )
}
