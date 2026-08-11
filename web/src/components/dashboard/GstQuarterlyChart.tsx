import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { rechartsDurationMs, rechartsEasing } from '../../motion/tokens'

interface QuarterRow {
  period: string
  collected: string
  itcs_claimable: string
  net_owing: string
}

function formatCurrency(n: number): string {
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

// dashboard_design.md §8's GST/HST Control Center. Collected and ITCs
// are neutral magnitudes (Financial Blue / neutral grey) -- neither is
// a "good" or "bad" outcome on its own, just money moving through the
// business on the CRA's behalf, per design.md's colour-polarity rule.
export default function GstQuarterlyChart({ rows }: { rows: QuarterRow[] }) {
  const data = rows.map((r) => ({
    period: r.period,
    collected: Number(r.collected),
    itcs: Number(r.itcs_claimable),
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-default)" vertical={false} />
        <XAxis dataKey="period" tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }} axisLine={{ stroke: 'var(--color-border-default)' }} tickLine={false} />
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
        <Bar
          dataKey="collected"
          name="Collected"
          fill="var(--color-accent-default)"
          radius={[2, 2, 0, 0]}
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        />
        <Bar
          dataKey="itcs"
          name="ITCs claimable"
          fill="var(--color-text-tertiary)"
          radius={[2, 2, 0, 0]}
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}
