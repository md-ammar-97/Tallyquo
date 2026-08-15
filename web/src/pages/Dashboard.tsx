import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { TriangleAlert } from 'lucide-react'
import { api, ApiError } from '../api'
import { staggerContainer, tileEntrance } from '../motion/tokens'
import KpiTile from '../components/dashboard/KpiTile'
import RevenueExpenseChart, { type PnlRow } from '../components/dashboard/RevenueExpenseChart'
import SafeToSpendWaterfall from '../components/dashboard/SafeToSpendWaterfall'
import ActualVsProjectedChart from '../components/dashboard/ActualVsProjectedChart'
import GstQuarterlyChart from '../components/dashboard/GstQuarterlyChart'
import AgingChart from '../components/dashboard/AgingChart'
import InvoiceStatusDonut from '../components/dashboard/InvoiceStatusDonut'
import RevenueByClientChart from '../components/dashboard/RevenueByClientChart'
import ExpenseCategoryDonut from '../components/dashboard/ExpenseCategoryDonut'

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

interface RevenueByClientRow {
  client_id: string
  client_name: string
  billed_cad: string
}

interface ExpenseByCategoryRow {
  category_id: string | null
  category_name: string
  amount: string
}

interface ReceiptCompleteness {
  total: number
  with_receipt: number
  missing: number
  pct: number | null
}

interface RecurringForecastRow {
  period: string
  amount: string
}

interface BusinessProfile {
  legal_name: string
  address_line1: string | null
  city: string | null
  region_code: string | null
  registration_status: string
  gst_hst_number: string | null
}

interface RecentExpense {
  id: string
  expense_date: string
  vendor: string | null
  amount_total: string
  created_at: string
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
  const [revenueByClient, setRevenueByClient] = useState<RevenueByClientRow[]>([])
  const [expenseByCategory, setExpenseByCategory] = useState<ExpenseByCategoryRow[]>([])
  const [receiptCompleteness, setReceiptCompleteness] = useState<ReceiptCompleteness | null>(null)
  const [recurringForecast, setRecurringForecast] = useState<RecurringForecastRow[]>([])
  const [profile, setProfile] = useState<BusinessProfile | null>(null)
  const [recentExpenses, setRecentExpenses] = useState<RecentExpense[]>([])
  const [priorYearProjection, setPriorYearProjection] = useState<Projection | null>(null)
  const [annualPnlRows, setAnnualPnlRows] = useState<PnlRow[]>([])

  async function loadProjection(year?: number) {
    try {
      const data = await api.get<Projection>(`/projection${year ? `?year=${year}` : ''}`)
      setProjection(data)
      setProjectionError(null)
      await loadTaxReserve(data.year)
      // Business Momentum (dashboard_design.md §19): current vs. prior
      // comparable period. A full month/quarter comparison would need
      // period-scoped projection support this endpoint doesn't have
      // (see the year-selector note above) -- year-over-year is what's
      // actually available, so that's the comparison built here.
      api.get<Projection>(`/projection?year=${data.year - 1}`).then(setPriorYearProjection).catch(() => setPriorYearProjection(null))
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
    api.get<PnlRow[]>('/reports/pnl?group_by=year').then(setAnnualPnlRows)
    api.get<AgingSummary>('/reports/aging/summary').then(setAgingSummary)
    api.get<RecentInvoice[]>('/invoices').then(setAllInvoices)
    api.get<RevenueByClientRow[]>('/reports/revenue-by-client').then(setRevenueByClient)
    api.get<ExpenseByCategoryRow[]>('/expenses/by-category').then(setExpenseByCategory)
    api.get<ReceiptCompleteness>('/expenses/receipt-completeness').then(setReceiptCompleteness)
    api.get<RecurringForecastRow[]>('/projection/recurring-forecast?months=3').then(setRecurringForecast)
    api.get<BusinessProfile | null>('/profile').then(setProfile)
    api.get<RecentExpense[]>('/expenses').then((rows) => setRecentExpenses(rows.slice(0, 5)))
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
  const overdueAmount = agingSummary ? Number(agingSummary.total_outstanding) - Number(agingSummary.not_due) : 0

  // Accountant Readiness (dashboard_design.md §21): a composite computed
  // client-side, not an opaque server-side score -- each factor and its
  // weight is visible right here, so "why is my score 80%" is always
  // answerable by reading this component, not a black box.
  const readinessFactors: { label: string; done: boolean; detail: string }[] = []
  if (profile) {
    readinessFactors.push({
      label: 'Business profile complete',
      done: !!(profile.legal_name && profile.address_line1 && profile.city),
      detail: profile.legal_name && profile.address_line1 && profile.city ? 'On file.' : 'Missing legal name or address.',
    })
    readinessFactors.push({
      label: 'GST/HST registration on file',
      done: profile.registration_status !== 'registered' || !!profile.gst_hst_number,
      detail:
        profile.registration_status === 'registered'
          ? profile.gst_hst_number
            ? 'Registered, BN on file.'
            : 'Registered but missing a BN number.'
          : 'Not registered -- not applicable.',
    })
  }
  if (receiptCompleteness) {
    readinessFactors.push({
      label: 'Expenses have receipts',
      done: receiptCompleteness.missing === 0,
      detail:
        receiptCompleteness.missing === 0
          ? 'All expenses supported.'
          : `${receiptCompleteness.missing} expense${receiptCompleteness.missing === 1 ? '' : 's'} missing a receipt.`,
    })
  }
  readinessFactors.push({
    label: 'No overdue invoices',
    done: overdueAmount <= 0.01,
    detail: overdueAmount > 0.01 ? `CAD ${overdueAmount.toFixed(2)} overdue.` : 'Nothing overdue.',
  })
  const readinessPct = readinessFactors.length
    ? Math.round((readinessFactors.filter((f) => f.done).length / readinessFactors.length) * 100)
    : 0

  // Needs Your Attention (dashboard_design.md §22): surfaced actions,
  // not just analytics. Priority order follows §22's own guidance --
  // compliance risk, then overdue money, then missing records, then
  // upcoming/informational items.
  const attentionItems: { level: 'high' | 'medium' | 'low' | 'info'; text: string; to: string; cta: string }[] = []
  if (projection?.threshold.escalation === 'overdue') {
    attentionItems.push({ level: 'high', text: 'GST/HST registration threshold crossed.', to: '/settings/profile', cta: 'Review registration' })
  } else if (projection?.threshold.escalation === 'attention') {
    attentionItems.push({ level: 'medium', text: `GST/HST threshold is at ${projection.threshold.pct_of_threshold}%.`, to: '/settings/profile', cta: 'Review threshold' })
  }
  if (overdueAmount > 0.01) {
    attentionItems.push({ level: 'high', text: `CAD ${overdueAmount.toFixed(2)} is overdue from clients.`, to: '/invoices?status=overdue', cta: 'View overdue invoices' })
  }
  if (receiptCompleteness && receiptCompleteness.missing > 0) {
    attentionItems.push({
      level: 'medium',
      text: `${receiptCompleteness.missing} expense${receiptCompleteness.missing === 1 ? '' : 's'} missing a receipt.`,
      to: '/expenses',
      cta: 'Review expenses',
    })
  }
  if (taxReserve && projection) {
    const shortfall = Number(projection.set_aside.total_estimated_tax_and_cpp) - Number(taxReserve.reserved_amount ?? 0)
    if (shortfall > 0.01) {
      attentionItems.push({ level: 'low', text: `Tax reserve is CAD ${shortfall.toFixed(2)} below the recommended amount.`, to: '#tax-reserve', cta: 'View calculation' })
    }
  }
  const upcomingRecurring = recurringForecast.find((r) => Number(r.amount) > 0)
  if (upcomingRecurring) {
    attentionItems.push({
      level: 'info',
      text: `CAD ${Number(upcomingRecurring.amount).toFixed(2)} in recurring revenue expected ${new Date(upcomingRecurring.period + 'T00:00:00').toLocaleDateString('en-CA', { month: 'long' })}.`,
      to: '/settings/recurring',
      cta: 'View recurring',
    })
  }

  // Recent Activity (dashboard_design.md §23): a lightweight feed, not a
  // full audit log -- merges the two data sources already fetched for
  // other sections (invoices, expenses) rather than a dedicated endpoint.
  const activity = [
    ...allInvoices.map((inv) => ({
      date: inv.invoice_date ?? '',
      text: `Invoice ${inv.number ?? '(draft)'} ${inv.status} -- ${inv.currency} ${inv.total}`,
      to: `/invoices/${inv.id}`,
    })),
    ...recentExpenses.map((exp) => ({
      date: exp.expense_date,
      text: `Expense logged -- ${exp.vendor ?? 'Uncategorized'} -- CAD ${exp.amount_total}`,
      to: '/expenses',
    })),
  ]
    .sort((a, b) => (a.date < b.date ? 1 : -1))
    .slice(0, 6)

  const yoyRows = annualPnlRows.filter((r) => r.period.startsWith(String(projection?.year ?? '')) || Number(r.period.slice(0, 4)) === (projection?.year ?? 0) - 1)
  const hasYoyData = annualPnlRows.some((r) => Number(r.period.slice(0, 4)) < (projection?.year ?? 0))

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
        <motion.div variants={staggerContainer} initial="initial" animate="animate">
          {projection.instalment_warning.applies && (
            <div
              className="block alert"
              style={{
                borderLeft: '3px solid var(--color-status-overdue)',
                background: 'var(--color-status-overdue-bg)',
              }}
            >
              <div className="block-body" style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <TriangleAlert size={18} color="var(--color-status-overdue)" style={{ flexShrink: 0, marginTop: 2 }} />
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
          <motion.div className="metric-grid" variants={staggerContainer} initial="initial" animate="animate">
            <KpiTile
              label="Revenue"
              value={formatDisplay(projection.ytd.income)}
              numericValue={Number(projection.ytd.income)}
              format={formatDisplay}
              sub="year to date, excludes tax collected"
            />
            <KpiTile
              label="Expenses"
              value={formatDisplay(projection.ytd.expenses)}
              numericValue={Number(projection.ytd.expenses)}
              format={formatDisplay}
              sub="year to date, deductible portion only"
            />
            <KpiTile
              label="Net income"
              value={formatDisplay(projection.ytd.net_income)}
              numericValue={Number(projection.ytd.net_income)}
              format={formatDisplay}
              sub="revenue minus expenses, year to date"
              polarity={Number(projection.ytd.net_income) >= 0 ? 'positive' : 'negative'}
            />
            <KpiTile
              label="Safe to spend"
              value={formatDisplay(safeToSpend)}
              numericValue={safeToSpend}
              format={formatDisplay}
              sub="full-year projected income, after recommended tax + CPP reserve"
              polarity={safeToSpend >= 0 ? 'positive' : 'negative'}
            />
          </motion.div>

          <motion.div className="metric-grid" variants={staggerContainer} initial="initial" animate="animate">
            <motion.div
              className={`metric-tile${assumptionsOpen ? ' expanded' : ''}`}
              style={{ borderLeft: '4px solid var(--color-tertiary-default)' }}
              variants={tileEntrance}
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
            </motion.div>

            <KpiTile
              label="GST/HST owing (this year)"
              value={formatDisplay(gstHeldTotal)}
              numericValue={Number(gstHeldTotal)}
              format={formatDisplay}
              sub="collected minus input tax credits -- never revenue"
            />
            <KpiTile
              label="Outstanding"
              value={formatDisplay(agingSummary?.total_outstanding ?? '0')}
              numericValue={Number(agingSummary?.total_outstanding ?? '0')}
              format={formatDisplay}
              sub={agingSummary ? `CAD ${Number(agingSummary.total_outstanding) - Number(agingSummary.not_due) > 0 ? (Number(agingSummary.total_outstanding) - Number(agingSummary.not_due)).toFixed(2) : '0.00'} overdue` : undefined}
              polarity={agingSummary && Number(agingSummary.total_outstanding) - Number(agingSummary.not_due) > 0 ? 'negative' : 'neutral'}
            />
            <KpiTile
              label="Projected annual revenue"
              value={formatDisplay(projection.income.active_projected_income)}
              numericValue={Number(projection.income.active_projected_income)}
              format={formatDisplay}
              sub={projection.income.mode === 'declared' ? 'your declared target' : 'straight-line extrapolation'}
            />
          </motion.div>

          <motion.div className="block" variants={tileEntrance}>
            <div className="block-header">
              <h2>Business performance</h2>
            </div>
            <div className="block-body">
              <RevenueExpenseChart rows={pnlRows} />
            </div>
          </motion.div>

          <motion.div className="dashboard-chart-grid" variants={staggerContainer}>
            <motion.div className="block" variants={tileEntrance}>
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
            </motion.div>
            <motion.div className="block" variants={tileEntrance}>
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
            </motion.div>
          </motion.div>

          <motion.div className="metric-grid" variants={staggerContainer}>
            {/* Tax Reserve progress (dashboard_design.md §7): the
                recommended figure is already computed above; this tracks
                what the user says they've actually moved into a reserve
                account. Careful language throughout -- "recommended
                reserve" and "shortfall", never "you owe", matching §7's
                explicit copy guidance. */}
            <motion.div className="metric-tile" variants={tileEntrance}>
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
            </motion.div>

            <motion.div className="metric-tile" variants={tileEntrance}>
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
            </motion.div>
          </motion.div>

          {/* GST/HST Control Center (dashboard_design.md §8) + AR Aging
              (§10) -- both already had a home in this app before this
              redesign (a plain quarterly table, and the client-level
              aging report); this adds the tenant-wide chart view each
              section's spec calls for, keeping the underlying data. */}
          <motion.div className="dashboard-chart-grid" variants={staggerContainer}>
            <motion.div className="block" variants={tileEntrance}>
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
            </motion.div>

            <motion.div className="block" variants={tileEntrance}>
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
            </motion.div>
          </motion.div>

          <motion.div className="block" variants={tileEntrance}>
            <div className="block-header">
              <h2>Invoice status</h2>
            </div>
            <div className="block-body">
              <InvoiceStatusDonut invoices={allInvoices} />
            </div>
          </motion.div>

          {/* Revenue by Client (dashboard_design.md §13) + Expense
              Category (§15). Monthly Expense Trend (§16) is deliberately
              not a separate chart -- the Business Performance chart
              above already plots monthly expenses as its own bar series,
              and a second standalone expense-only trend chart would just
              repeat that data, not add anything. */}
          <motion.div className="dashboard-chart-grid" variants={staggerContainer}>
            <motion.div className="block" variants={tileEntrance}>
              <div className="block-header">
                <h2>Revenue by client</h2>
              </div>
              <div className="block-body">
                <RevenueByClientChart rows={revenueByClient} />
                {revenueByClient.length > 0 && (
                  <p className="caption" style={{ marginTop: 8 }}>
                    {(
                      (Number(revenueByClient[0].billed_cad) / revenueByClient.reduce((s, r) => s + Number(r.billed_cad), 0)) *
                      100
                    ).toFixed(0)}
                    % of revenue currently comes from {revenueByClient[0].client_name}.
                  </p>
                )}
              </div>
            </motion.div>
            <motion.div className="block" variants={tileEntrance}>
              <div className="block-header">
                <h2>Expenses by category</h2>
              </div>
              <div className="block-body">
                <ExpenseCategoryDonut rows={expenseByCategory} />
              </div>
            </motion.div>
          </motion.div>

          <motion.div className="metric-grid" variants={staggerContainer}>
            {/* Receipt Completeness (§17) */}
            {receiptCompleteness && receiptCompleteness.total > 0 && (
              <motion.div className="metric-tile" variants={tileEntrance}>
                <div className="metric-label">Receipts on file</div>
                <div className="metric-value">{receiptCompleteness.pct?.toFixed(0) ?? 0}%</div>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: `${receiptCompleteness.pct ?? 0}%` }} />
                </div>
                <p className="caption metric-sub">
                  {receiptCompleteness.with_receipt} / {receiptCompleteness.total} expenses supported
                  {receiptCompleteness.missing > 0 && ` -- ${receiptCompleteness.missing} missing`}
                </p>
              </motion.div>
            )}

            {/* Recurring Revenue (§18) */}
            <motion.div className="metric-tile" variants={tileEntrance}>
              <div className="metric-label">Recurring revenue (next month)</div>
              <div className="metric-value display">{formatDisplay(recurringForecast[0]?.amount ?? '0')}</div>
              <p className="caption metric-sub">from active recurring invoice schedules</p>
            </motion.div>

            {/* Accountant Readiness (§21) */}
            {readinessFactors.length > 0 && (
              <motion.div className="metric-tile" variants={tileEntrance}>
                <div className="metric-label">Accountant readiness</div>
                <div className="metric-value">{readinessPct}%</div>
                <div className="progress-bar">
                  <div className={`progress-bar-fill${readinessPct < 100 ? ' attention' : ''}`} style={{ width: `${readinessPct}%` }} />
                </div>
                <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {readinessFactors
                    .filter((f) => !f.done)
                    .map((f) => (
                      <p key={f.label} className="caption">
                        {f.label}: {f.detail}
                      </p>
                    ))}
                </div>
              </motion.div>
            )}
          </motion.div>

          {/* Business Momentum (§19): this year vs. last year YTD, the
              comparison actually available from a year-scoped
              projection -- see the year-selector note above. */}
          {priorYearProjection && (
            <motion.div className="block" variants={tileEntrance}>
              <div className="block-header">
                <h2>Business momentum</h2>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th className="amount">{projection.year}</th>
                    <th className="amount">{priorYearProjection.year}</th>
                    <th className="amount">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      ['Revenue', Number(projection.ytd.income), Number(priorYearProjection.ytd.income)],
                      ['Expenses', Number(projection.ytd.expenses), Number(priorYearProjection.ytd.expenses)],
                      ['Net income', Number(projection.ytd.net_income), Number(priorYearProjection.ytd.net_income)],
                    ] as [string, number, number][]
                  ).map(([label, current, prior]) => {
                    const pctChange = prior !== 0 ? ((current - prior) / Math.abs(prior)) * 100 : null
                    return (
                      <tr key={label}>
                        <td>{label}</td>
                        <td className="amount">CAD {current.toFixed(2)}</td>
                        <td className="amount">CAD {prior.toFixed(2)}</td>
                        <td className="amount" style={{ color: pctChange != null && pctChange >= 0 ? 'var(--color-secondary-default)' : pctChange != null ? 'var(--color-status-overdue)' : undefined }}>
                          {pctChange != null ? `${pctChange >= 0 ? '+' : ''}${pctChange.toFixed(0)}%` : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </motion.div>
          )}

          {/* Year-over-Year (§20): gated behind at least one prior year
              of data existing, per the spec. */}
          {hasYoyData && yoyRows.length > 1 && (
            <motion.div className="block" variants={tileEntrance}>
              <div className="block-header">
                <h2>Year-over-year</h2>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Year</th>
                    <th className="amount">Revenue</th>
                    <th className="amount">Expenses</th>
                    <th className="amount">Net income</th>
                  </tr>
                </thead>
                <tbody>
                  {yoyRows.map((r) => (
                    <tr key={r.period}>
                      <td>{r.period.slice(0, 4)}</td>
                      <td className="amount">CAD {r.income}</td>
                      <td className="amount">CAD {r.expenses}</td>
                      <td className="amount">CAD {r.net_income}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </motion.div>
          )}

          {/* Needs Your Attention (§22): surfaced actions, prioritized
              compliance risk first, then overdue money, then missing
              records, then informational items -- per §22's own
              guidance. */}
          {attentionItems.length > 0 && (
            <motion.div className="block" variants={tileEntrance}>
              <div className="block-header">
                <h2>Needs your attention</h2>
              </div>
              <div className="block-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {attentionItems.map((item, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                    <span
                      style={{
                        color:
                          item.level === 'high'
                            ? 'var(--color-status-overdue)'
                            : item.level === 'medium'
                              ? 'var(--color-tertiary-default)'
                              : 'var(--color-text-primary)',
                      }}
                    >
                      {item.text}
                    </span>
                    <Link className="link-button" to={item.to}>
                      {item.cta}
                    </Link>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Recent Activity (§23): a lightweight feed merging the invoice
          and expense data already fetched for other sections -- not a
          full audit log. */}
      {activity.length > 0 && (
        <div className="block">
          <div className="block-header">
            <h2>Recent activity</h2>
          </div>
          <div className="block-body" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {activity.map((a, i) => (
              <Link key={i} to={a.to} style={{ display: 'flex', justifyContent: 'space-between', color: 'inherit', textDecoration: 'none' }}>
                <span>{a.text}</span>
                <span className="caption">{a.date}</span>
              </Link>
            ))}
          </div>
        </div>
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
