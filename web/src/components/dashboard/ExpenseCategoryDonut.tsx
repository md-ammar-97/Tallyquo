import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

interface Row {
  category_id: string | null
  category_name: string
  amount: string
}

function formatCurrency(n: number): string {
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

// Carbon's dataviz categorical palette (design.md §13, --color-chart-1..6)
// -- neutral multi-category series, deliberately not the green/red
// polarity colours, since no expense category is inherently "good" or
// "bad" relative to another.
const CATEGORY_COLORS = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
  'var(--color-chart-6)',
  'var(--color-accent-default)',
  'var(--color-tertiary-default)',
]

export default function ExpenseCategoryDonut({ rows }: { rows: Row[] }) {
  const data = rows.filter((r) => Number(r.amount) > 0).map((r) => ({ name: r.category_name, value: Number(r.amount) }))

  if (data.length === 0) {
    return <p className="caption">No expenses logged yet.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
          {data.map((_d, i) => (
            <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value) => formatCurrency(Number(value))}
          contentStyle={{ background: 'var(--color-bg-default)', border: '1px solid var(--color-border-default)', fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
