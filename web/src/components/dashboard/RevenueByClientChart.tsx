import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { rechartsDurationMs, rechartsEasing } from '../../motion/tokens'

interface Row {
  client_id: string
  client_name: string
  billed_cad: string
}

function formatCurrency(n: number): string {
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

// dashboard_design.md §13: client concentration, horizontal bar. Neutral
// Financial Blue throughout -- which client bills the most isn't a
// polarity question, and the concentration insight is delivered as text
// (the caller shows "% of revenue from your largest client"), not colour.
export default function RevenueByClientChart({ rows }: { rows: Row[] }) {
  const top = rows.slice(0, 8).map((r) => ({ name: r.client_name, value: Number(r.billed_cad) }))

  if (top.length === 0) {
    return <p className="caption">No billed clients yet.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={Math.max(160, top.length * 36)}>
      <BarChart data={top} layout="vertical" margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-default)" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }} axisLine={false} tickLine={false} tickFormatter={(v: number) => formatCurrency(v)} />
        <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }} axisLine={false} tickLine={false} width={110} />
        <Tooltip
          formatter={(value) => formatCurrency(Number(value))}
          contentStyle={{ background: 'var(--color-bg-default)', border: '1px solid var(--color-border-default)', fontSize: 12 }}
        />
        <Bar
          dataKey="value"
          fill="var(--color-accent-default)"
          radius={[0, 2, 2, 0]}
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}
