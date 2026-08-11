import { useEffect, useRef, useState } from 'react'
import { animate, useReducedMotion } from 'motion/react'
import { duration, ease } from './tokens'

// Animates a KPI figure from its previously-displayed value to a newly
// arrived one. Deliberately does NOT animate on first mount (jumps
// straight to the real figure) -- callers only mount this once real data
// is available, so there is never a placeholder value to climb from.
// `formatter` re-runs on every animation frame so the displayed string
// always carries the caller's real currency/number formatting.
export function useCountUp(value: number | undefined, formatter?: (n: number) => string): string | null {
  const reducedMotion = useReducedMotion()
  const [display, setDisplay] = useState<string | null>(value !== undefined && formatter ? formatter(value) : null)
  const prevValue = useRef(value)
  const isFirstRender = useRef(true)

  useEffect(() => {
    if (value === undefined || !formatter) return

    if (isFirstRender.current) {
      isFirstRender.current = false
      prevValue.current = value
      setDisplay(formatter(value))
      return
    }

    if (reducedMotion || prevValue.current === value) {
      prevValue.current = value
      setDisplay(formatter(value))
      return
    }

    const from = prevValue.current ?? value
    const controls = animate(from, value, {
      duration: duration.slow01,
      ease: ease.standardProductive,
      onUpdate: (v) => setDisplay(formatter(v)),
    })
    prevValue.current = value
    return () => controls.stop()
  }, [value, formatter, reducedMotion])

  return display
}
