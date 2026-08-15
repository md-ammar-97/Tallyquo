// A single hero KPI card (dashboard_design.md §3). Colour polarity is
// opt-in and deliberately narrow: green/red apply only to genuinely
// positive/negative financial outcomes (net income sign, safe-to-spend,
// overdue/outstanding amounts) -- never to neutral-magnitude figures
// like GST/HST collected, which stay plain even though a bigger number
// isn't "bad". See design.md's colour-polarity rule.
import { motion } from 'motion/react'
import { useCountUp } from '../../motion/useCountUp'
import { tileEntrance, tileHover } from '../../motion/tokens'
import { Card, CardContent } from '@/components/ui/card'

export type Polarity = 'positive' | 'negative' | 'neutral'

interface Props {
  label: string
  value: string
  /** Raw numeric value + its formatter, for the count-up tween on data
      arrival. Both optional -- omit either to fall back to a static
      `value`; never animates on first mount (see useCountUp). */
  numericValue?: number
  format?: (n: number) => string
  sub?: string
  polarity?: Polarity
  children?: React.ReactNode
}

const POLARITY_CLASS: Record<Polarity, string> = {
  positive: 'text-positive',
  negative: 'text-negative',
  neutral: 'text-ink',
}

export default function KpiTile({ label, value, numericValue, format, sub, polarity = 'neutral', children }: Props) {
  const animatedValue = useCountUp(numericValue, format)
  return (
    <motion.div variants={tileEntrance} whileHover={tileHover.whileHover} whileTap={tileHover.whileTap}>
      <Card className="h-full py-5">
        <CardContent className="flex flex-col gap-1">
          <p className="text-body-sm font-semibold text-mute">{label}</p>
          <p className={`font-display text-display-xs ${POLARITY_CLASS[polarity]}`}>{animatedValue ?? value}</p>
          {sub && <p className="text-caption text-mute">{sub}</p>}
          {children}
        </CardContent>
      </Card>
    </motion.div>
  )
}
