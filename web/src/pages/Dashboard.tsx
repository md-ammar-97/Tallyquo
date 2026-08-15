import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { TriangleAlert } from 'lucide-react'
import { api, ApiError } from '../api'
import { staggerContainer, tileEntrance } from '../motion/tokens'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
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
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-display-sm text-ink">How much is mine?</h1>
          <p className="text-body-sm text-mute">
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
          <div className="flex items-center gap-3 text-body-sm font-medium">
            <button className="text-mute transition-colors hover:text-ink" onClick={() => changeYear(-1)}>
              &larr; {projection.year - 1}
            </button>
            <button className="text-mute transition-colors hover:text-ink" onClick={() => changeYear(1)}>
              {projection.year + 1} &rarr;
            </button>
          </div>
        )}
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4">
          <p className="text-body-sm text-body">
            Set up your business profile and a client, then issue a correctly-taxed invoice in under two minutes.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" asChild>
              <Link to="/settings/profile">1. Business profile</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/clients">2. Add a client</Link>
            </Button>
            <Button asChild>
              <Link to="/invoices/new">3. Issue an invoice</Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      {projectionError && (
        <Card>
          <CardContent>
            <p className="text-body-sm text-mute">{projectionError}</p>
          </CardContent>
        </Card>
      )}

      {projection && (
        <motion.div className="flex flex-col gap-6" variants={staggerContainer} initial="initial" animate="animate">
          {projection.instalment_warning.applies && (
            <div className="flex items-start gap-3 rounded-xl border border-negative/30 bg-negative-bg/5 py-4 pr-4 pl-4 border-l-4 border-l-negative">
              <TriangleAlert size={18} className="mt-0.5 shrink-0 text-negative" />
              <div>
                <strong className="text-body-sm font-semibold text-negative">Quarterly instalment warning</strong>
                <p className="mt-1 text-body-sm text-mute">
                  Projected net income tax + CPP owing (CAD {projection.instalment_warning.projected_net_tax_owing})
                  is over CAD {projection.instalment_warning.threshold} -- the CRA may expect quarterly instalments.
                  Confirm with your accountant.
                </p>
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
          <motion.div
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
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

          <motion.div
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
            <motion.div variants={tileEntrance} className="sm:col-span-2">
              <Card className="h-full border-l-4 border-l-warning py-5">
                <CardContent className="flex flex-col gap-1">
                  <p className="text-body-sm font-semibold text-mute">Tax + CPP reserve</p>
                  <p className="font-display text-display-xs text-ink">
                    {formatDisplay(projection.set_aside.total_estimated_tax_and_cpp)}
                  </p>
                  <p className="text-caption text-mute">
                    {projection.income.mode === 'declared' ? 'based on declared income' : 'estimate'}
                    {projection.income.derived.is_low_confidence &&
                      projection.income.mode === 'derived' &&
                      ' -- low confidence, early in the year'}
                  </p>
                  <button
                    className="mt-1 self-start text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
                    onClick={() => setAssumptionsOpen((o) => !o)}
                  >
                    {assumptionsOpen ? 'Hide logic' : 'View logic'}
                  </button>
                  {assumptionsOpen && (
                    <div className="mt-2 flex flex-col gap-1.5 border-t border-divider pt-3">
                      <div className="flex justify-between text-body-sm">
                        <span className="text-mute">Province</span>
                        <span>{projection.jurisdiction}</span>
                      </div>
                      <div className="flex justify-between text-body-sm">
                        <span className="text-mute">Tax year</span>
                        <span>{projection.year}</span>
                      </div>
                      <div className="flex justify-between text-body-sm">
                        <span className="text-mute">Net business income</span>
                        <span>CAD {projection.set_aside.net_business_income}</span>
                      </div>
                      <div className="flex justify-between text-body-sm">
                        <span className="text-mute">Federal income tax (est.)</span>
                        <span>CAD {projection.set_aside.federal_tax.total_tax}</span>
                      </div>
                      <div className="flex justify-between text-body-sm">
                        <span className="text-mute">{projection.jurisdiction} income tax (est.)</span>
                        <span>CAD {projection.set_aside.provincial_tax.total_tax}</span>
                      </div>
                      <div className="flex justify-between text-body-sm">
                        <span className="text-mute">Tax brackets applied</span>
                        <span>
                          {projection.set_aside.federal_tax.bands.length} federal, {projection.set_aside.provincial_tax.bands.length}{' '}
                          provincial
                        </span>
                      </div>
                      <div className="flex justify-between text-body-sm">
                        <span className="text-mute">CPP (self-employed, both halves)</span>
                        <span>CAD {projection.set_aside.cpp.total_contribution}</span>
                      </div>
                      <div className="flex justify-between text-body-sm">
                        <span className="text-mute">Recommended set-aside</span>
                        <span>{projection.set_aside.recommended_set_aside_pct}% of net income</span>
                      </div>
                      <p className="mt-1 text-caption text-mute">
                        Estimate only, not tax advice. Based on{' '}
                        {projection.income.mode === 'declared'
                          ? 'your declared annual income'
                          : `${projection.income.derived.method.replace(/_/g, ' ')}`}{' '}
                        of CAD {projection.income.active_projected_income}, accrual basis (by invoice and expense date,
                        not when cash actually changed hands).
                      </p>

                      {projection.income.mode === 'declared' ? (
                        <p className="text-caption text-mute">
                          Derived (extrapolated) estimate: CAD {projection.income.derived.projected_annual_income}
                          {projection.income.variance_from_derived && ` (gap: CAD ${projection.income.variance_from_derived})`}{' '}
                          <button className="font-medium text-ink underline underline-offset-2" onClick={handleClearDeclared}>
                            Use derived instead
                          </button>
                        </p>
                      ) : editingDeclared ? (
                        <form onSubmit={handleSaveDeclared} className="mt-2 flex items-center gap-2">
                          <input
                            type="number"
                            step="0.01"
                            placeholder="Declared annual income"
                            value={declaredDraft}
                            onChange={(e) => setDeclaredDraft(e.target.value)}
                            className="h-9 w-40 rounded-md border border-ink px-3 text-body-sm"
                            required
                          />
                          <Button type="submit" size="sm">Save</Button>
                          <button
                            type="button"
                            className="text-body-sm font-medium text-mute hover:text-ink"
                            onClick={() => setEditingDeclared(false)}
                          >
                            Cancel
                          </button>
                        </form>
                      ) : (
                        <button
                          className="mt-1 self-start text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
                          onClick={() => setEditingDeclared(true)}
                        >
                          Declare your own income figure instead
                        </button>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
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

          <motion.div variants={tileEntrance}>
            <Card>
              <CardHeader>
                <CardTitle className="font-display text-display-xs font-semibold text-ink">Business performance</CardTitle>
              </CardHeader>
              <CardContent>
                <RevenueExpenseChart rows={pnlRows} />
              </CardContent>
            </Card>
          </motion.div>

          <motion.div className="grid grid-cols-1 gap-4 lg:grid-cols-2" variants={staggerContainer}>
            <motion.div variants={tileEntrance}>
              <Card className="h-full">
                <CardHeader>
                  <CardTitle className="font-display text-display-xs font-semibold text-ink">Where your revenue goes</CardTitle>
                </CardHeader>
                <CardContent>
                  <SafeToSpendWaterfall
                    netBusinessIncome={Number(projection.set_aside.net_business_income)}
                    federalTax={Number(projection.set_aside.federal_tax.total_tax)}
                    provincialTax={Number(projection.set_aside.provincial_tax.total_tax)}
                    cpp={Number(projection.set_aside.cpp.total_contribution)}
                    jurisdiction={projection.jurisdiction}
                  />
                </CardContent>
              </Card>
            </motion.div>
            <motion.div variants={tileEntrance}>
              <Card className="h-full">
                <CardHeader>
                  <CardTitle className="font-display text-display-xs font-semibold text-ink">Actual vs. projected revenue</CardTitle>
                </CardHeader>
                <CardContent>
                  <ActualVsProjectedChart
                    rows={pnlRows}
                    year={projection.year}
                    projectedAnnualIncome={Number(projection.income.active_projected_income)}
                    declaredAnnualIncome={projection.income.declared_annual_income ? Number(projection.income.declared_annual_income) : null}
                  />
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>

          <motion.div className="grid grid-cols-1 gap-4 sm:grid-cols-2" variants={staggerContainer}>
            {/* Tax Reserve progress (dashboard_design.md §7): the
                recommended figure is already computed above; this tracks
                what the user says they've actually moved into a reserve
                account. Careful language throughout -- "recommended
                reserve" and "shortfall", never "you owe", matching §7's
                explicit copy guidance. */}
            <motion.div variants={tileEntrance}>
              <Card className="h-full py-5">
                <CardContent className="flex flex-col gap-1">
                  <p className="text-body-sm font-semibold text-mute">Tax reserve progress</p>
                  {(() => {
                    const recommended = Number(projection.set_aside.total_estimated_tax_and_cpp)
                    const reserved = Number(taxReserve?.reserved_amount ?? 0)
                    const pct = recommended > 0 ? Math.min(100, (reserved / recommended) * 100) : 0
                    const shortfall = recommended - reserved
                    return (
                      <>
                        <p className="font-display text-display-xs text-ink">{pct.toFixed(0)}%</p>
                        <Progress value={pct} className={pct < 100 ? '[&_[data-slot=progress-indicator]]:bg-warning' : undefined} />
                        <p className="mt-1 text-caption text-mute">
                          CAD {reserved.toFixed(2)} reserved of CAD {recommended.toFixed(2)} recommended
                          {shortfall > 0.01 && ` -- CAD ${shortfall.toFixed(2)} below the recommended amount`}
                        </p>
                        {editingReserve ? (
                          <form onSubmit={handleSaveReserve} className="mt-2 flex items-center gap-2">
                            <input
                              type="number"
                              step="0.01"
                              placeholder="Amount actually reserved"
                              value={reserveDraft}
                              onChange={(e) => setReserveDraft(e.target.value)}
                              className="h-9 w-40 rounded-md border border-ink px-3 text-body-sm"
                              required
                            />
                            <Button type="submit" size="sm">Save</Button>
                            <button
                              type="button"
                              className="text-body-sm font-medium text-mute hover:text-ink"
                              onClick={() => setEditingReserve(false)}
                            >
                              Cancel
                            </button>
                          </form>
                        ) : (
                          <button
                            className="mt-1 self-start text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute"
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
                </CardContent>
              </Card>
            </motion.div>

            <motion.div variants={tileEntrance}>
              <Card className="h-full py-5">
                <CardContent className="flex flex-col gap-1">
                  <p className="text-body-sm font-semibold text-mute">Threshold tracker</p>
                  <p className="font-display text-display-xs text-ink">{projection.threshold.pct_of_threshold}%</p>
                  <Progress
                    value={Math.min(100, Number(projection.threshold.pct_of_threshold))}
                    className={projection.threshold.escalation === 'overdue' ? '[&_[data-slot=progress-indicator]]:bg-negative' : projection.threshold.escalation === 'attention' ? '[&_[data-slot=progress-indicator]]:bg-warning' : undefined}
                  />
                  <p className="mt-1 text-caption text-mute">
                    {Number(projection.threshold.threshold) - Number(projection.threshold.rolling_revenue) > 0
                      ? `CAD ${(Number(projection.threshold.threshold) - Number(projection.threshold.rolling_revenue)).toFixed(2)} from the CAD ${projection.threshold.threshold} registration threshold. Crossing it changes what you must charge.`
                      : 'Threshold reached -- registration is required.'}
                  </p>
                  <p className="text-caption text-mute">
                    Based on this account only -- the $30,000 threshold is shared across any associated businesses you
                    also run.
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>

          {/* GST/HST Control Center (dashboard_design.md §8) + AR Aging
              (§10) -- both already had a home in this app before this
              redesign (a plain quarterly table, and the client-level
              aging report); this adds the tenant-wide chart view each
              section's spec calls for, keeping the underlying data. */}
          <motion.div className="grid grid-cols-1 gap-4 lg:grid-cols-2" variants={staggerContainer}>
            <motion.div variants={tileEntrance}>
              <Card className="h-full">
                <CardHeader>
                  <CardTitle className="font-display text-display-xs font-semibold text-ink">GST/HST control center</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <GstQuarterlyChart rows={projection.quarterly_net_owing} />
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Quarter</TableHead>
                        <TableHead>Collected</TableHead>
                        <TableHead>ITCs claimable</TableHead>
                        <TableHead>Net owing</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {projection.quarterly_net_owing.map((q) => (
                        <TableRow key={q.period}>
                          <TableCell>{q.period}</TableCell>
                          <TableCell>CAD {q.collected}</TableCell>
                          <TableCell>CAD {q.itcs_claimable}</TableCell>
                          <TableCell>CAD {q.net_owing}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </motion.div>

            <motion.div variants={tileEntrance}>
              <Card className="h-full">
                <CardHeader>
                  <CardTitle className="font-display text-display-xs font-semibold text-ink">Accounts receivable aging</CardTitle>
                </CardHeader>
                <CardContent>
                  {agingSummary && (
                    <>
                      <AgingChart summary={agingSummary} />
                      {Number(agingSummary.total_outstanding) - Number(agingSummary.not_due) > 0 && (
                        <p className="mt-2 text-body-sm text-negative">
                          CAD {(Number(agingSummary.total_outstanding) - Number(agingSummary.not_due)).toFixed(2)} is
                          currently overdue.
                        </p>
                      )}
                    </>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>

          <motion.div variants={tileEntrance}>
            <Card>
              <CardHeader>
                <CardTitle className="font-display text-display-xs font-semibold text-ink">Invoice status</CardTitle>
              </CardHeader>
              <CardContent>
                <InvoiceStatusDonut invoices={allInvoices} />
              </CardContent>
            </Card>
          </motion.div>

          {/* Revenue by Client (dashboard_design.md §13) + Expense
              Category (§15). Monthly Expense Trend (§16) is deliberately
              not a separate chart -- the Business Performance chart
              above already plots monthly expenses as its own bar series,
              and a second standalone expense-only trend chart would just
              repeat that data, not add anything. */}
          <motion.div className="grid grid-cols-1 gap-4 lg:grid-cols-2" variants={staggerContainer}>
            <motion.div variants={tileEntrance}>
              <Card className="h-full">
                <CardHeader>
                  <CardTitle className="font-display text-display-xs font-semibold text-ink">Revenue by client</CardTitle>
                </CardHeader>
                <CardContent>
                  <RevenueByClientChart rows={revenueByClient} />
                  {revenueByClient.length > 0 && (
                    <p className="mt-2 text-body-sm text-mute">
                      {(
                        (Number(revenueByClient[0].billed_cad) / revenueByClient.reduce((s, r) => s + Number(r.billed_cad), 0)) *
                        100
                      ).toFixed(0)}
                      % of revenue currently comes from {revenueByClient[0].client_name}.
                    </p>
                  )}
                </CardContent>
              </Card>
            </motion.div>
            <motion.div variants={tileEntrance}>
              <Card className="h-full">
                <CardHeader>
                  <CardTitle className="font-display text-display-xs font-semibold text-ink">Expenses by category</CardTitle>
                </CardHeader>
                <CardContent>
                  <ExpenseCategoryDonut rows={expenseByCategory} />
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>

          <motion.div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" variants={staggerContainer}>
            {/* Receipt Completeness (§17) */}
            {receiptCompleteness && receiptCompleteness.total > 0 && (
              <motion.div variants={tileEntrance}>
                <Card className="h-full py-5">
                  <CardContent className="flex flex-col gap-1">
                    <p className="text-body-sm font-semibold text-mute">Receipts on file</p>
                    <p className="font-display text-display-xs text-ink">{receiptCompleteness.pct?.toFixed(0) ?? 0}%</p>
                    <Progress value={receiptCompleteness.pct ?? 0} />
                    <p className="mt-1 text-caption text-mute">
                      {receiptCompleteness.with_receipt} / {receiptCompleteness.total} expenses supported
                      {receiptCompleteness.missing > 0 && ` -- ${receiptCompleteness.missing} missing`}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Recurring Revenue (§18) */}
            <motion.div variants={tileEntrance}>
              <Card className="h-full py-5">
                <CardContent className="flex flex-col gap-1">
                  <p className="text-body-sm font-semibold text-mute">Recurring revenue (next month)</p>
                  <p className="font-display text-display-xs text-ink">{formatDisplay(recurringForecast[0]?.amount ?? '0')}</p>
                  <p className="text-caption text-mute">from active recurring invoice schedules</p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Accountant Readiness (§21) */}
            {readinessFactors.length > 0 && (
              <motion.div variants={tileEntrance}>
                <Card className="h-full py-5">
                  <CardContent className="flex flex-col gap-1">
                    <p className="text-body-sm font-semibold text-mute">Accountant readiness</p>
                    <p className="font-display text-display-xs text-ink">{readinessPct}%</p>
                    <Progress value={readinessPct} className={readinessPct < 100 ? '[&_[data-slot=progress-indicator]]:bg-warning' : undefined} />
                    <div className="mt-1 flex flex-col gap-0.5">
                      {readinessFactors
                        .filter((f) => !f.done)
                        .map((f) => (
                          <p key={f.label} className="text-caption text-mute">
                            {f.label}: {f.detail}
                          </p>
                        ))}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </motion.div>

          {/* Business Momentum (§19): this year vs. last year YTD, the
              comparison actually available from a year-scoped
              projection -- see the year-selector note above. */}
          {priorYearProjection && (
            <motion.div variants={tileEntrance}>
              <Card>
                <CardHeader>
                  <CardTitle className="font-display text-display-xs font-semibold text-ink">Business momentum</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Metric</TableHead>
                        <TableHead className="text-right">{projection.year}</TableHead>
                        <TableHead className="text-right">{priorYearProjection.year}</TableHead>
                        <TableHead className="text-right">Change</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(
                        [
                          ['Revenue', Number(projection.ytd.income), Number(priorYearProjection.ytd.income)],
                          ['Expenses', Number(projection.ytd.expenses), Number(priorYearProjection.ytd.expenses)],
                          ['Net income', Number(projection.ytd.net_income), Number(priorYearProjection.ytd.net_income)],
                        ] as [string, number, number][]
                      ).map(([label, current, prior]) => {
                        const pctChange = prior !== 0 ? ((current - prior) / Math.abs(prior)) * 100 : null
                        return (
                          <TableRow key={label}>
                            <TableCell>{label}</TableCell>
                            <TableCell className="text-right">CAD {current.toFixed(2)}</TableCell>
                            <TableCell className="text-right">CAD {prior.toFixed(2)}</TableCell>
                            <TableCell
                              className={`text-right ${pctChange != null && pctChange >= 0 ? 'text-positive' : pctChange != null ? 'text-negative' : ''}`}
                            >
                              {pctChange != null ? `${pctChange >= 0 ? '+' : ''}${pctChange.toFixed(0)}%` : '—'}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* Year-over-Year (§20): gated behind at least one prior year
              of data existing, per the spec. */}
          {hasYoyData && yoyRows.length > 1 && (
            <motion.div variants={tileEntrance}>
              <Card>
                <CardHeader>
                  <CardTitle className="font-display text-display-xs font-semibold text-ink">Year-over-year</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Year</TableHead>
                        <TableHead className="text-right">Revenue</TableHead>
                        <TableHead className="text-right">Expenses</TableHead>
                        <TableHead className="text-right">Net income</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {yoyRows.map((r) => (
                        <TableRow key={r.period}>
                          <TableCell>{r.period.slice(0, 4)}</TableCell>
                          <TableCell className="text-right">CAD {r.income}</TableCell>
                          <TableCell className="text-right">CAD {r.expenses}</TableCell>
                          <TableCell className="text-right">CAD {r.net_income}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* Needs Your Attention (§22): surfaced actions, prioritized
              compliance risk first, then overdue money, then missing
              records, then informational items -- per §22's own
              guidance. */}
          {attentionItems.length > 0 && (
            <motion.div variants={tileEntrance}>
              <Card>
                <CardHeader>
                  <CardTitle className="font-display text-display-xs font-semibold text-ink">Needs your attention</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {attentionItems.map((item, i) => (
                    <div key={i} className="flex items-center justify-between gap-3">
                      <span
                        className={
                          item.level === 'high'
                            ? 'text-body-sm text-negative'
                            : item.level === 'medium'
                              ? 'text-body-sm text-warning-deep'
                              : 'text-body-sm text-ink'
                        }
                      >
                        {item.text}
                      </span>
                      <Link className="shrink-0 text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute" to={item.to}>
                        {item.cta}
                      </Link>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Recent Activity (§23): a lightweight feed merging the invoice
          and expense data already fetched for other sections -- not a
          full audit log. */}
      {activity.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-display-xs font-semibold text-ink">Recent activity</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {activity.map((a, i) => (
              <Link key={i} to={a.to} className="flex justify-between text-ink no-underline hover:text-mute">
                <span className="text-body-sm">{a.text}</span>
                <span className="text-caption text-mute">{a.date}</span>
              </Link>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Recent invoices</CardTitle>
          <Link className="text-body-sm font-medium text-ink underline underline-offset-2 hover:text-mute" to="/invoices">
            View all
          </Link>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Client</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Tax treatment</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentInvoices.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell>
                    <Link className="text-ink underline underline-offset-2 hover:text-mute" to={`/invoices/${inv.id}`}>
                      {inv.client_name ?? '—'}
                    </Link>
                  </TableCell>
                  <TableCell>{inv.invoice_date ?? '—'}</TableCell>
                  <TableCell>
                    {inv.tax_treatment_snapshot && (
                      <Badge variant="secondary" className="capitalize">
                        {inv.tax_treatment_snapshot.replace(/_/g, ' ')}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {inv.currency} {inv.total}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={inv.status === 'overdue' ? 'destructive' : 'secondary'}
                      className={`capitalize ${inv.status === 'paid' ? 'bg-positive/15 text-positive-deep' : ''}`}
                    >
                      {inv.status.replace(/_/g, ' ')}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
              {recentInvoices.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-6 text-center text-body-sm text-mute">
                    No invoices yet.
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
