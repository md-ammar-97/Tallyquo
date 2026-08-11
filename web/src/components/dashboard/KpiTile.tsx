// A single hero KPI card (dashboard_design.md §3). Colour polarity is
// opt-in and deliberately narrow: green/red apply only to genuinely
// positive/negative financial outcomes (net income sign, safe-to-spend,
// overdue/outstanding amounts) -- never to neutral-magnitude figures
// like GST/HST collected, which stay plain even though a bigger number
// isn't "bad". See design.md's colour-polarity rule.

export type Polarity = 'positive' | 'negative' | 'neutral'

interface Props {
  label: string
  value: string
  sub?: string
  polarity?: Polarity
  accent?: 'gold' | 'blue'
  children?: React.ReactNode
}

const POLARITY_VAR: Record<Polarity, string | null> = {
  positive: 'var(--color-secondary-default)',
  negative: 'var(--color-status-overdue)',
  neutral: null,
}

export default function KpiTile({ label, value, sub, polarity = 'neutral', accent, children }: Props) {
  const color = POLARITY_VAR[polarity]
  return (
    <div
      className="metric-tile"
      style={accent ? { borderLeft: `4px solid var(--color-${accent === 'gold' ? 'tertiary' : 'accent'}-default)` } : undefined}
    >
      <div className="metric-label">{label}</div>
      <div className="metric-value display" style={color ? { color } : undefined}>
        {value}
      </div>
      {sub && <p className="caption metric-sub">{sub}</p>}
      {children}
    </div>
  )
}
