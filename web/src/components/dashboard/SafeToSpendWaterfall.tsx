import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { rechartsDurationMs, rechartsEasing } from '../../motion/tokens'

interface Props {
  netBusinessIncome: number
  federalTax: number
  provincialTax: number
  cpp: number
  jurisdiction: string
}

function formatCurrency(n: number): string {
  return n.toLocaleString('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

// dashboard_design.md §5's own example starts from raw Revenue, then
// Expenses, then tax/CPP. Built from Net Business Income instead (one
// fewer step) -- set_aside's tax/CPP figures are computed from the
// *active projected annual* net income basis, not the YTD actual
// revenue/expenses this dashboard shows elsewhere, and there's no
// projected-annual-expenses figure in GET /projection to bridge the
// two consistently. Starting from net income keeps every step on the
// same basis rather than forcing numbers that wouldn't actually
// reconcile -- a deliberate, noted deviation, not an oversight.
export default function SafeToSpendWaterfall({ netBusinessIncome, federalTax, provincialTax, cpp, jurisdiction }: Props) {
  const afterFederal = netBusinessIncome - federalTax
  const afterProvincial = afterFederal - provincialTax
  const safeToSpend = afterProvincial - cpp

  const steps = [
    { name: 'Net income', base: 0, value: netBusinessIncome, display: netBusinessIncome, kind: 'start' },
    { name: 'Federal tax', base: afterFederal, value: federalTax, display: -federalTax, kind: 'deduction' },
    { name: `${jurisdiction} tax`, base: afterProvincial, value: provincialTax, display: -provincialTax, kind: 'deduction' },
    { name: 'CPP', base: safeToSpend, value: cpp, display: -cpp, kind: 'deduction' },
    { name: 'Safe to spend', base: 0, value: safeToSpend, display: safeToSpend, kind: 'end' },
  ]

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={steps} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-divider)" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 12, fill: 'var(--color-mute)' }} axisLine={{ stroke: 'var(--color-divider)' }} tickLine={false} />
        <YAxis
          tick={{ fontSize: 12, fill: 'var(--color-mute)' }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v: number) => formatCurrency(v)}
          width={80}
        />
        <Tooltip
          formatter={(_value, _name, entry) => [formatCurrency(entry.payload.display), 'Amount']}
          contentStyle={{ background: 'var(--color-canvas)', border: '1px solid var(--color-divider)', borderRadius: 12, fontSize: 12 }}
        />
        {/* Invisible base bar floats the visible bar to the right height. */}
        <Bar dataKey="base" stackId="waterfall" fill="transparent" isAnimationActive={false} />
        <Bar
          dataKey="value"
          stackId="waterfall"
          radius={[2, 2, 0, 0]}
          animationDuration={rechartsDurationMs.entrance}
          animationEasing={rechartsEasing.entrance}
        >
          {steps.map((step, i) => (
            <Cell
              key={i}
              // Deductions use Set-aside Gold, not Error Red -- a tax/CPP
              // obligation is an expected deduction, not a wrong outcome,
              // and gold already carries "tax liability" meaning
              // consistently elsewhere in this app (design.md §2.3).
              fill={
                step.kind === 'start' || step.kind === 'end'
                  ? 'var(--color-positive)'
                  : 'var(--color-warning)'
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
