import { Bar, CartesianGrid, ComposedChart, Line, XAxis, YAxis } from 'recharts'
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent, type ChartConfig } from '@/components/ui/chart'
import { rechartsDurationMs, rechartsEasing } from '../../motion/tokens'

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

// Revenue and expenses are bars (brand lime / neutral grey -- neither
// carries polarity, they're just magnitudes; lime is the CTA identity
// colour, not a chart series, so it's used here as a plain neutral, not
// a "this is good" signal). Net income is a dashed neutral line rather
// than green/red, since a single stroke can't change colour mid-line if
// it crosses zero across the year -- see design.md's colour-polarity rule.
const chartConfig = {
  income: { label: 'Revenue', color: 'var(--color-primary-active)' },
  expenses: { label: 'Expenses', color: 'var(--color-mute)' },
  net_income: { label: 'Net income', color: 'var(--color-ink)' },
} satisfies ChartConfig

export default function RevenueExpenseChart({ rows }: { rows: PnlRow[] }) {
  const data = rows.map((r) => ({
    period: r.period,
    label: formatMonth(r.period),
    income: Number(r.income),
    expenses: Number(r.expenses),
    net_income: Number(r.net_income),
  }))

  if (data.length === 0) {
    return <p className="text-body-sm text-mute">Not enough data yet -- issue an invoice or log an expense to see this chart.</p>
  }

  return (
    <ChartContainer config={chartConfig} className="aspect-auto h-[280px] w-full">
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-divider)" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 12, fill: 'var(--color-mute)' }} axisLine={{ stroke: 'var(--divider)' }} tickLine={false} />
        <YAxis
          tick={{ fontSize: 12, fill: 'var(--color-mute)' }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v: number) => formatCurrency(v)}
          width={80}
        />
        <ChartTooltip content={<ChartTooltipContent formatter={(value) => formatCurrency(Number(value))} />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar
          dataKey="income"
          fill="var(--color-income)"
          radius={[2, 2, 0, 0]}
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        />
        <Bar
          dataKey="expenses"
          fill="var(--color-expenses)"
          radius={[2, 2, 0, 0]}
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        />
        <Line
          type="monotone"
          dataKey="net_income"
          stroke="var(--color-net_income)"
          strokeWidth={2}
          strokeDasharray="4 3"
          dot={{ r: 3 }}
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        />
      </ComposedChart>
    </ChartContainer>
  )
}
