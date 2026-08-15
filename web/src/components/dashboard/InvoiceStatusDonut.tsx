import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { rechartsDurationMs, rechartsEasing } from '../../motion/tokens'

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

  // Recharts' pie-sector entrance animation interpolates `fill` through
  // react-smooth, which can't parse CSS custom properties as colours (it
  // silently resolves var(...) to black once the animation settles) --
  // so these are literal hex values (matching tailwind.css's tokens),
  // not var() strings like every other (non-animated-fill) chart here.
  const COLORS: Record<string, string> = {
    paid: '#2ead4b', // --color-positive
    issued: '#38c8ff', // --color-chart-2 / --color-accent-cyan
    partially_paid: '#ffd11a', // --color-warning
    overdue: '#d03238', // --color-negative
    draft: '#868685', // --color-mute
    cancelled: '#ffc091', // --color-chart-3 / --color-accent-orange
  }

  const data = Object.entries(counts).map(([status, count]) => ({
    name: status.replace(/_/g, ' '),
    value: count,
    color: COLORS[status] ?? '#d03238',
  }))

  if (data.length === 0) {
    return <p className="text-body-sm text-mute">No invoices yet.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius={55}
          outerRadius={85}
          paddingAngle={2}
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        >
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value, name) => [value, name]}
          contentStyle={{ background: 'var(--color-canvas)', border: '1px solid var(--color-divider)', borderRadius: 12, fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12, textTransform: 'capitalize' }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
