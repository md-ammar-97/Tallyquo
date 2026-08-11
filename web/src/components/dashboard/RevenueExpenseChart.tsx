import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export interface PnlRow {
  period: string
  income: string
  expenses: string
  net_income: string
}

function formatMonth(period: string): string {
  const d = new Date(period + 'T00:00:00')
  return d.toLocaleDateString('en-CA', { month: 'short' })
}

function formatCurrency(n: number): string {
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

// Revenue and expenses are bars (Financial Blue / neutral grey -- neither
// carries polarity, they're just magnitudes). Net income is a dashed
// neutral line rather than green/red, since a single stroke can't
// change colour mid-line if it crosses zero across the year -- see
// design.md's colour-polarity rule (KpiTile.tsx has the fuller note).
export default function RevenueExpenseChart({ rows }: { rows: PnlRow[] }) {
  const data = rows.map((r) => ({
    period: r.period,
    label: formatMonth(r.period),
    income: Number(r.income),
    expenses: Number(r.expenses),
    net_income: Number(r.net_income),
  }))

  if (data.length === 0) {
    return <p className="caption">Not enough data yet -- issue an invoice or log an expense to see this chart.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-default)" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }} axisLine={{ stroke: 'var(--color-border-default)' }} tickLine={false} />
        <YAxis
          tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v: number) => formatCurrency(v)}
          width={80}
        />
        <Tooltip
          formatter={(value) => formatCurrency(Number(value))}
          contentStyle={{ background: 'var(--color-bg-default)', border: '1px solid var(--color-border-default)', fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="income" name="Revenue" fill="var(--color-accent-default)" radius={[2, 2, 0, 0]} />
        <Bar dataKey="expenses" name="Expenses" fill="var(--color-text-tertiary)" radius={[2, 2, 0, 0]} />
        <Line
          type="monotone"
          dataKey="net_income"
          name="Net income"
          stroke="var(--color-text-primary)"
          strokeWidth={2}
          strokeDasharray="4 3"
          dot={{ r: 3 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
