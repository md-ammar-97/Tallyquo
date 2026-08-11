import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface AgingSummary {
  not_due: string
  bucket_0_30: string
  bucket_31_60: string
  bucket_61_90: string
  bucket_90_plus: string
  total_outstanding: string
}

function formatCurrency(n: number): string {
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

// dashboard_design.md §10: most buckets are magnitude, not polarity --
// "not due" isn't a warning, and 1-60 days overdue is routine enough
// not to alarm over, so those stay neutral Financial Blue rather than a
// red gradient that would overstate how bad every bucket is. Only 90+
// days gets Error Red -- that's genuinely the one bucket signalling a
// real collection problem, not just normal payment lag.
export default function AgingChart({ summary }: { summary: AgingSummary }) {
  const data = [
    { label: 'Not due', value: Number(summary.not_due) },
    { label: '1-30 days', value: Number(summary.bucket_0_30) },
    { label: '31-60 days', value: Number(summary.bucket_31_60) },
    { label: '61-90 days', value: Number(summary.bucket_61_90) },
    { label: '90+ days', value: Number(summary.bucket_90_plus) },
  ]

  if (Number(summary.total_outstanding) === 0) {
    return <p className="caption">Nothing outstanding right now.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-default)" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v: number) => formatCurrency(v)}
        />
        <YAxis type="category" dataKey="label" tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }} axisLine={false} tickLine={false} width={80} />
        <Tooltip
          formatter={(value) => formatCurrency(Number(value))}
          contentStyle={{ background: 'var(--color-bg-default)', border: '1px solid var(--color-border-default)', fontSize: 12 }}
        />
        <Bar dataKey="value" radius={[0, 2, 2, 0]}>
          {data.map((_d, i) => (
            <Cell key={i} fill={i === 4 ? 'var(--color-status-overdue)' : 'var(--color-accent-default)'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
