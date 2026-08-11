import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

interface Invoice {
  status: string
}

// dashboard_design.md §11: a compact donut of invoice status counts --
// explicitly called out in its own §28 chart inventory as a legitimate
// donut use case (distribution of a small fixed set of categories),
// unlike the places that document warns against pie/donut for precise
// comparison. Client-side tally of the same GET /invoices list Recent
// Invoices already fetches -- no new backend call.
export default function InvoiceStatusDonut({ invoices }: { invoices: Invoice[] }) {
  const counts: Record<string, number> = {}
  for (const inv of invoices) {
    counts[inv.status] = (counts[inv.status] ?? 0) + 1
  }

  const COLORS: Record<string, string> = {
    paid: 'var(--color-secondary-default)',
    issued: 'var(--color-accent-default)',
    partially_paid: 'var(--color-tertiary-default)',
    overdue: 'var(--color-status-overdue)',
    draft: 'var(--color-text-tertiary)',
    cancelled: 'var(--color-border-strong)',
  }

  const data = Object.entries(counts).map(([status, count]) => ({
    name: status.replace(/_/g, ' '),
    value: count,
    color: COLORS[status] ?? 'var(--color-chart-6)',
  }))

  if (data.length === 0) {
    return <p className="caption">No invoices yet.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value, name) => [value, name]}
          contentStyle={{ background: 'var(--color-bg-default)', border: '1px solid var(--color-border-default)', fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12, textTransform: 'capitalize' }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
