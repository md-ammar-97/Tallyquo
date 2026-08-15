import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { rechartsDurationMs, rechartsEasing } from '../../motion/tokens'

interface Row {
  category_id: string | null
  category_name: string
  amount: string
}

function formatCurrency(n: number): string {
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

// Dataviz categorical palette (design.md's colour-polarity rule, chart-1..6
// built from positive/accent-cyan/accent-orange/warning/mute/negative --
// never brand lime, reserved for the CTA identity) -- neutral multi-
// category series, since no expense category is inherently "good" or
// "bad" relative to another. Two extra neutral shades extend past 6
// categories without repeating or falling back to lime.
//
// Literal hex values, not var(...) strings: Recharts' pie-sector entrance
// animation interpolates `fill` through react-smooth, which can't parse
// CSS custom properties as colours -- it silently resolves var(...) to
// black once the animation settles (unlike Bar/Line fills, which never
// animate colour and render var() natively via the browser's own CSS
// engine).
const CATEGORY_COLORS = [
  '#2ead4b', // --color-chart-1 / --color-positive
  '#38c8ff', // --color-chart-2 / --color-accent-cyan
  '#ffc091', // --color-chart-3 / --color-accent-orange
  '#ffd11a', // --color-chart-4 / --color-warning
  '#868685', // --color-chart-5 / --color-mute
  '#d03238', // --color-chart-6 / --color-negative
  '#163300', // --color-ink-deep
  '#454745', // --color-body
]

export default function ExpenseCategoryDonut({ rows }: { rows: Row[] }) {
  const data = rows.filter((r) => Number(r.amount) > 0).map((r) => ({ name: r.category_name, value: Number(r.amount) }))

  if (data.length === 0) {
    return <p className="text-body-sm text-mute">No expenses logged yet.</p>
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
          {data.map((_d, i) => (
            <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value) => formatCurrency(Number(value))}
          contentStyle={{ background: 'var(--color-canvas)', border: '1px solid var(--color-divider)', borderRadius: 12, fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
