import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PnlRow } from './RevenueExpenseChart'
import { rechartsDurationMs, rechartsEasing } from '../../motion/tokens'

interface Props {
  rows: PnlRow[]
  year: number
  projectedAnnualIncome: number
  declaredAnnualIncome: number | null
}

function formatCurrency(n: number): string {
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// Cumulative actual revenue (solid) up to the last month with real data,
// then a straight-line projected continuation (dashed) to the year-end
// target -- dashboard_design.md §6's own sketch. Built entirely from
// GET /reports/pnl (already fetched for the trend chart) and
// GET /projection's existing income figures -- no new backend work.
export default function ActualVsProjectedChart({ rows, year, projectedAnnualIncome, declaredAnnualIncome }: Props) {
  const byMonth = new Map(rows.filter((r) => r.period.startsWith(String(year))).map((r) => [Number(r.period.slice(5, 7)), Number(r.income)]))
  const lastActualMonth = Math.max(0, ...Array.from(byMonth.keys()))

  let cumulative = 0
  const data: { label: string; actual: number | null; projected: number | null }[] = []
  for (let m = 1; m <= 12; m++) {
    if (m <= lastActualMonth) {
      cumulative += byMonth.get(m) ?? 0
      data.push({ label: MONTH_LABELS[m - 1], actual: cumulative, projected: m === lastActualMonth ? cumulative : null })
    } else {
      const remainingMonths = 12 - lastActualMonth
      const step = remainingMonths > 0 ? (projectedAnnualIncome - cumulative) / remainingMonths : 0
      const projectedValue = m === lastActualMonth + 1 ? cumulative + step : null
      data.push({ label: MONTH_LABELS[m - 1], actual: null, projected: projectedValue })
    }
  }
  // Fill the dashed line across every remaining month via linear
  // interpolation between the last actual point and the year-end target.
  let carried = cumulative
  for (let m = lastActualMonth + 1; m <= 12; m++) {
    const remainingMonths = 12 - lastActualMonth
    const step = remainingMonths > 0 ? (projectedAnnualIncome - cumulative) / remainingMonths : 0
    carried += step
    data[m - 1].projected = carried
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-divider)" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 12, fill: 'var(--color-mute)' }} axisLine={{ stroke: 'var(--color-divider)' }} tickLine={false} />
        <YAxis
          tick={{ fontSize: 12, fill: 'var(--color-mute)' }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v: number) => formatCurrency(v)}
          width={80}
        />
        <Tooltip
          formatter={(value) => (value == null ? '—' : formatCurrency(Number(value)))}
          contentStyle={{ background: 'var(--color-canvas)', border: '1px solid var(--color-divider)', borderRadius: 12, fontSize: 12 }}
        />
        {declaredAnnualIncome != null && (
          <ReferenceLine
            y={declaredAnnualIncome}
            stroke="var(--color-warning-deep)"
            strokeDasharray="2 2"
            label={{ value: 'Target', fontSize: 11, fill: 'var(--color-warning-deep)', position: 'insideTopRight' }}
          />
        )}
        <Line
          type="monotone"
          dataKey="actual"
          name="Actual"
          stroke="var(--color-positive)"
          strokeWidth={2}
          dot={{ r: 3 }}
          connectNulls={false}
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        />
        <Line
          type="monotone"
          dataKey="projected"
          name="Projected"
          stroke="var(--color-positive)"
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={{ r: 3 }}
          connectNulls
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
