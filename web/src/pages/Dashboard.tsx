import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { WarningAltFilled } from '@carbon/icons-react'
import { api, ApiError } from '../api'
import KpiTile from '../components/dashboard/KpiTile'
import RevenueExpenseChart, { type PnlRow } from '../components/dashboard/RevenueExpenseChart'
import SafeToSpendWaterfall from '../components/dashboard/SafeToSpendWaterfall'
import ActualVsProjectedChart from '../components/dashboard/ActualVsProjectedChart'
import GstQuarterlyChart from '../components/dashboard/GstQuarterlyChart'
import AgingChart from '../components/dashboard/AgingChart'
import InvoiceStatusDonut from '../components/dashboard/InvoiceStatusDonut'

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

interface YtdActuals {
  income: string
  expenses: string
  net_income: string
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
  ytd: YtdActuals
}

interface AgingSummary {
  not_due: string
  bucket_0_30: string
  bucket_31_60: string
  bucket_61_90: string
  bucket_90_plus: string
  total_outstanding: string
}

interface RecentInvoice {
  id: string
  number: string | null
  client_name: string | null
  invoice_date: string | null
  status: string
  tax_treatment_snapshot: string | null
  currency: string
  total: string
}

interface TaxReserve {
  year: number
  reserved_amount: string | null
}

const RECENT_INVOICES_LIMIT = 8

function formatDisplay(amount: string | number): string {
  const n = Number(amount)
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

export default function Dashboard() {
  const [projection, setProjection] = useState<Projection | null>(null)
  const [projectionError, setProjectionError] = useState<string | null>(null)
  const [pnlRows, setPnlRows] = useState<PnlRow[]>([])
  const [agingSummary, setAgingSummary] = useState<AgingSummary | null>(null)
  const [assumptionsOpen, setAssumptionsOpen] = useState(false)
  const [declaredDraft, setDeclaredDraft] = useState('')
  const [editingDeclared, setEditingDeclared] = useState(false)
  const [allInvoices, setAllInvoices] = useState<RecentInvoice[]>([])
  const [taxReserve, setTaxReserve] = useState<TaxReserve | null>(null)
  const [editingReserve, setEditingReserve] = useState(false)
  const [reserveDraft, setReserveDraft] = useState('')

  async function loadProjection(year?: number) {
    try {
      const data = await api.get<Projection>(`/projection${year ? `?year=${year}` : ''}`)
      setProjection(data)
      setProjectionError(null)
      await loadTaxReserve(data.year)
    } catch (err) {
      setProjection(null)
      setProjectionError(err instanceof ApiError ? err.message : 'Could not load projection.')
    }
  }

  async function loadTaxReserve(year: number) {
    const data = await api.get<TaxReserve>(`/projection/tax-reserve/${year}`)
    setTaxReserve(data)
  }

  useEffect(() => {
    loadProjection()
    api.get<PnlRow[]>('/reports/pnl?group_by=month').then(setPnlRows)
    api.get<AgingSummary>('/reports/aging/summary').then(setAgingSummary)
    api.get<RecentInvoice[]>('/invoices').then(setAllInvoices)
  }, [])

  const recentInvoices = allInvoices.slice(0, RECENT_INVOICES_LIMIT)

  async function handleSaveReserve(e: React.FormEvent) {
    e.preventDefault()
    if (!projection) return
    await api.put('/projection/tax-reserve', { year: projection.year, reserved_amount: reserveDraft })
    setEditingReserve(false)
    await loadTaxReserve(projection.year)
  }

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

  const safeToSpend = projection
    ? Number(projection.set_aside.net_business_income) - Number(projection.set_aside.total_estimated_tax_and_cpp)
    : 0
  const gstHeldTotal = projection
    ? projection.quarterly_net_owing.reduce((sum, q) => sum + Number(q.net_owing), 0)
    : 0

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>How much is mine?</h1>
          <p className="caption" style={{ marginTop: -8, marginBottom: 16 }}>
            {projection ? `Year-to-date projection for ${projection.year}` : 'Year-to-date projection'}
          </p>
        </div>
        {projection && (
          // Full period granularity (This month/Last month/This
          // quarter/Last quarter/Last year/Custom, dashboard_design.md
          // §2) is deliberately narrower here: the hero tax/CPP figures
          // are inherently annual concepts (income tax and CPP are
          // calculated on a calendar year, not an arbitrary window), so
          // a year selector -- not a full date-range picker -- is what
          // actually stays meaningful across everything on this page. A
          // noted v1 scope, not an oversight.
          <span>
            <button className="link-button" onClick={() => changeYear(-1)}>
              &larr; {projection.year - 1}
            </button>{' '}
            <button className="link-button" onClick={() => changeYear(1)}>
              {projection.year + 1} &rarr;
            </button>
          </span>
        )}
      </div>

      <div className="block">
        <div className="block-body">
          <p style={{ marginBottom: 16 }}>
            Set up your business profile and a client, then issue a correctly-taxed invoice in under two minutes.
          </p>
          <Link to="/settings/profile">
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
          {projection.instalment_warning.applies && (
            <div
              className="block alert"
              style={{
                borderLeft: '3px solid var(--color-status-overdue)',
                background: 'var(--color-status-overdue-bg)',
              }}
            >
              <div className="block-body" style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <WarningAltFilled size={18} color="var(--color-status-overdue)" style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <strong style={{ color: 'var(--color-status-overdue)' }}>Quarterly instalment warning</strong>
                  <p className="caption" style={{ marginTop: 4 }}>
                    Projected net income tax + CPP owing (CAD {projection.instalment_warning.projected_net_tax_owing})
                    is over CAD {projection.instalment_warning.threshold} -- the CRA may expect quarterly instalments.
                    Confirm with your accountant.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Hero KPIs (dashboard_design.md §3): Revenue/Expenses/Net
              Income/Safe-to-Spend on row 1, Tax+CPP Reserve/GST-HST
              Owing/Outstanding/Projected Annual Revenue on row 2. Green/
              red apply only where a figure is a genuine financial
              outcome (Net income sign, Safe to spend, Outstanding) --
              GST/HST owing and the projected/reserve figures stay
              neutral, matching design.md's colour-polarity rule. */}
          <div className="metric-grid">
            <KpiTile label="Revenue" value={formatDisplay(projection.ytd.income)} sub="year to date, excludes tax collected" />
            <KpiTile label="Expenses" value={formatDisplay(projection.ytd.expenses)} sub="year to date, deductible portion only" />
            <KpiTile
              label="Net income"
              value={formatDisplay(projection.ytd.net_income)}
              sub="revenue minus expenses, year to date"
              polarity={Number(projection.ytd.net_income) >= 0 ? 'positive' : 'negative'}
            />
            <KpiTile
              label="Safe to spend"
              value={formatDisplay(safeToSpend)}
              sub="full-year projected income, after recommended tax + CPP reserve"
              polarity={safeToSpend >= 0 ? 'positive' : 'negative'}
            />
          </div>

          <div className="metric-grid">
            <div
              className={`metric-tile${assumptionsOpen ? ' expanded' : ''}`}
              style={{ borderLeft: '4px solid var(--color-tertiary-default)' }}
            >
              <div className="metric-label">Tax + CPP reserve</div>
              <div className="metric-value display">{formatDisplay(projection.set_aside.total_estimated_tax_and_cpp)}</div>
              <p className="caption metric-sub">
                {projection.income.mode === 'declared' ? 'based on declared income' : 'estimate'}
                {projection.income.derived.is_low_confidence &&
                  projection.income.mode === 'derived' &&
                  ' -- low confidence, early in the year'}
              </p>
              <button className="assumptions-toggle" onClick={() => setAssumptionsOpen((o) => !o)}>
                {assumptionsOpen ? 'Hide logic' : 'View logic'}
              </button>
              {assumptionsOpen && (
                <div className="assumptions-list">
                  <div className="row">
                    <span className="label">Province</span>
                    <span>{projection.jurisdiction}</span>
                  </div>
                  <div className="row">
                    <span className="label">Tax year</span>
                    <span>{projection.year}</span>
                  </div>
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
                    <span className="label">Tax brackets applied</span>
                    <span>
                      {projection.set_aside.federal_tax.bands.length} federal, {projection.set_aside.provincial_tax.bands.length}{' '}
                      provincial
                    </span>
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
                    Estimate only, not tax advice. Based on{' '}
                    {projection.income.mode === 'declared'
                      ? 'your declared annual income'
                      : `${projection.income.derived.method.replace(/_/g, ' ')}`}{' '}
                    of CAD {projection.income.active_projected_income}, accrual basis (by invoice and expense date,
                    not when cash actually changed hands).
                  </p>

                  {projection.income.mode === 'declared' ? (
                    <p className="caption">
                      Derived (extrapolated) estimate: CAD {projection.income.derived.projected_annual_income}
                      {projection.income.variance_from_derived && ` (gap: CAD ${projection.income.variance_from_derived})`}{' '}
                      <button className="link-button" onClick={handleClearDeclared}>
                        Use derived instead
                      </button>
                    </p>
                  ) : editingDeclared ? (
                    <form
                      onSubmit={handleSaveDeclared}
                      style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}
                    >
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
                      <button type="button" className="link-button" onClick={() => setEditingDeclared(false)}>
                        Cancel
                      </button>
                    </form>
                  ) : (
                    <button className="link-button" onClick={() => setEditingDeclared(true)}>
                      Declare your own income figure instead
                    </button>
                  )}
                </div>
              )}
            </div>

            <KpiTile
              label="GST/HST owing (this year)"
              value={formatDisplay(gstHeldTotal)}
              sub="collected minus input tax credits -- never revenue"
            />
            <KpiTile
              label="Outstanding"
              value={formatDisplay(agingSummary?.total_outstanding ?? '0')}
              sub={agingSummary ? `CAD ${Number(agingSummary.total_outstanding) - Number(agingSummary.not_due) > 0 ? (Number(agingSummary.total_outstanding) - Number(agingSummary.not_due)).toFixed(2) : '0.00'} overdue` : undefined}
              polarity={agingSummary && Number(agingSummary.total_outstanding) - Number(agingSummary.not_due) > 0 ? 'negative' : 'neutral'}
            />
            <KpiTile
              label="Projected annual revenue"
              value={formatDisplay(projection.income.active_projected_income)}
              sub={projection.income.mode === 'declared' ? 'your declared target' : 'straight-line extrapolation'}
            />
          </div>

          <div className="block">
            <div className="block-header">
              <h2>Business performance</h2>
            </div>
            <div className="block-body">
              <RevenueExpenseChart rows={pnlRows} />
            </div>
          </div>

          <div className="dashboard-chart-grid">
            <div className="block">
              <div className="block-header">
                <h2>Where your revenue goes</h2>
              </div>
              <div className="block-body">
                <SafeToSpendWaterfall
                  netBusinessIncome={Number(projection.set_aside.net_business_income)}
                  federalTax={Number(projection.set_aside.federal_tax.total_tax)}
                  provincialTax={Number(projection.set_aside.provincial_tax.total_tax)}
                  cpp={Number(projection.set_aside.cpp.total_contribution)}
                  jurisdiction={projection.jurisdiction}
                />
              </div>
            </div>
            <div className="block">
              <div className="block-header">
                <h2>Actual vs. projected revenue</h2>
              </div>
              <div className="block-body">
                <ActualVsProjectedChart
                  rows={pnlRows}
                  year={projection.year}
                  projectedAnnualIncome={Number(projection.income.active_projected_income)}
                  declaredAnnualIncome={projection.income.declared_annual_income ? Number(projection.income.declared_annual_income) : null}
                />
              </div>
            </div>
          </div>

          <div className="metric-grid">
            {/* Tax Reserve progress (dashboard_design.md §7): the
                recommended figure is already computed above; this tracks
                what the user says they've actually moved into a reserve
                account. Careful language throughout -- "recommended
                reserve" and "shortfall", never "you owe", matching §7's
                explicit copy guidance. */}
            <div className="metric-tile">
              <div className="metric-label">Tax reserve progress</div>
              {(() => {
                const recommended = Number(projection.set_aside.total_estimated_tax_and_cpp)
                const reserved = Number(taxReserve?.reserved_amount ?? 0)
                const pct = recommended > 0 ? Math.min(100, (reserved / recommended) * 100) : 0
                const shortfall = recommended - reserved
                return (
                  <>
                    <div className="metric-value">{pct.toFixed(0)}%</div>
                    <div className="progress-bar">
                      <div
                        className={`progress-bar-fill${pct < 100 ? ' attention' : ''}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p className="caption metric-sub">
                      CAD {reserved.toFixed(2)} reserved of CAD {recommended.toFixed(2)} recommended
                      {shortfall > 0.01 && ` -- CAD ${shortfall.toFixed(2)} below the recommended amount`}
                    </p>
                    {editingReserve ? (
                      <form onSubmit={handleSaveReserve} style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
                        <input
                          type="number"
                          step="0.01"
                          placeholder="Amount actually reserved"
                          value={reserveDraft}
                          onChange={(e) => setReserveDraft(e.target.value)}
                          style={{ width: 160 }}
                          required
                        />
                        <button type="submit">Save</button>
                        <button type="button" className="link-button" onClick={() => setEditingReserve(false)}>
                          Cancel
                        </button>
                      </form>
                    ) : (
                      <button
                        className="assumptions-toggle"
                        onClick={() => {
                          setReserveDraft(taxReserve?.reserved_amount ?? '')
                          setEditingReserve(true)
                        }}
                      >
                        Update reserved amount
                      </button>
                    )}
                  </>
                )
              })()}
            </div>

            <div className="metric-tile">
              <div className="metric-label">Threshold tracker</div>
              <div className="metric-value">{projection.threshold.pct_of_threshold}%</div>
              <div className="progress-bar">
                <div
                  className={`progress-bar-fill ${projection.threshold.escalation !== 'ok' ? projection.threshold.escalation : ''}`}
                  style={{ width: `${Math.min(100, Number(projection.threshold.pct_of_threshold))}%` }}
                />
              </div>
              <p className="caption metric-sub">
                {Number(projection.threshold.threshold) - Number(projection.threshold.rolling_revenue) > 0
                  ? `CAD ${(Number(projection.threshold.threshold) - Number(projection.threshold.rolling_revenue)).toFixed(2)} from the CAD ${projection.threshold.threshold} registration threshold. Crossing it changes what you must charge.`
                  : 'Threshold reached -- registration is required.'}
              </p>
              <p className="caption" style={{ marginTop: 4 }}>
                Based on this account only -- the $30,000 threshold is shared across any associated businesses you
                also run.
              </p>
            </div>
          </div>

          {/* GST/HST Control Center (dashboard_design.md §8) + AR Aging
              (§10) -- both already had a home in this app before this
              redesign (a plain quarterly table, and the client-level
              aging report); this adds the tenant-wide chart view each
              section's spec calls for, keeping the underlying data. */}
          <div className="dashboard-chart-grid">
            <div className="block">
              <div className="block-header">
                <h2>GST/HST control center</h2>
              </div>
              <div className="block-body">
                <GstQuarterlyChart rows={projection.quarterly_net_owing} />
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

            <div className="block">
              <div className="block-header">
                <h2>Accounts receivable aging</h2>
              </div>
              <div className="block-body">
                {agingSummary && (
                  <>
                    <AgingChart summary={agingSummary} />
                    {Number(agingSummary.total_outstanding) - Number(agingSummary.not_due) > 0 && (
                      <p className="caption" style={{ marginTop: 8, color: 'var(--color-status-overdue)' }}>
                        CAD {(Number(agingSummary.total_outstanding) - Number(agingSummary.not_due)).toFixed(2)} is
                        currently overdue.
                      </p>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="block">
            <div className="block-header">
              <h2>Invoice status</h2>
            </div>
            <div className="block-body">
              <InvoiceStatusDonut invoices={allInvoices} />
            </div>
          </div>
        </>
      )}

      <div className="block">
        <div className="block-header">
          <h2>Recent invoices</h2>
          <Link className="link-button" to="/invoices">
            View all
          </Link>
        </div>
        <table>
          <thead>
            <tr>
              <th>Client</th>
              <th>Date</th>
              <th>Tax treatment</th>
              <th>Amount</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {recentInvoices.map((inv) => (
              <tr key={inv.id}>
                <td>
                  <Link to={`/invoices/${inv.id}`}>{inv.client_name ?? '—'}</Link>
                </td>
                <td>{inv.invoice_date ?? '—'}</td>
                <td>
                  {inv.tax_treatment_snapshot && (
                    <span className={`badge ${inv.tax_treatment_snapshot}`}>
                      {inv.tax_treatment_snapshot.replace(/_/g, ' ')}
                    </span>
                  )}
                </td>
                <td className="amount">
                  {inv.currency} {inv.total}
                </td>
                <td>
                  <span className={`badge ${inv.status}`}>{inv.status.replace(/_/g, ' ')}</span>
                </td>
              </tr>
            ))}
            {recentInvoices.length === 0 && (
              <tr>
                <td colSpan={5} className="caption" style={{ padding: 24 }}>
                  No invoices yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
