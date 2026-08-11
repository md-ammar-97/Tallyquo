import {
  durationFast01,
  durationFast02,
  durationModerate01,
  durationModerate02,
  durationSlow01,
  durationSlow02,
  easings,
} from '@carbon/motion'
import type { Variants } from 'motion/react'

function msToSeconds(ms: string): number {
  return parseFloat(ms) / 1000
}

// Motion's `ease` transition prop takes a 4-number cubic-bezier tuple;
// @carbon/motion ships its curves as CSS `cubic-bezier(...)` strings.
function toBezierTuple(css: string): [number, number, number, number] {
  const [x1, y1, x2, y2] = css.match(/-?[\d.]+/g)!.map(Number)
  return [x1, y1, x2, y2]
}

export const duration = {
  fast01: msToSeconds(durationFast01), // 0.07s -- hover/press micro-feedback
  fast02: msToSeconds(durationFast02), // 0.11s
  moderate01: msToSeconds(durationModerate01), // 0.15s
  moderate02: msToSeconds(durationModerate02), // 0.24s -- tile/panel entrance
  slow01: msToSeconds(durationSlow01), // 0.4s -- page transitions, count-ups, chart draw-in
  slow02: msToSeconds(durationSlow02), // 0.7s
}

export const ease = {
  standardProductive: toBezierTuple(easings.standard.productive),
  standardExpressive: toBezierTuple(easings.standard.expressive),
  entranceProductive: toBezierTuple(easings.entrance.productive),
  entranceExpressive: toBezierTuple(easings.entrance.expressive),
  exitProductive: toBezierTuple(easings.exit.productive),
  exitExpressive: toBezierTuple(easings.exit.expressive),
}

// Recharts' animationEasing prop accepts a raw CSS cubic-bezier() string,
// but types it as a template literal with no spaces between numbers --
// @carbon/motion's strings have spaces ("cubic-bezier(0.4, 0.14, ...)"),
// so re-serialize from the already-parsed tuples above rather than
// passing the source string straight through.
function toRechartsBezier(tuple: [number, number, number, number]): `cubic-bezier(${number},${number},${number},${number})` {
  return `cubic-bezier(${tuple[0]},${tuple[1]},${tuple[2]},${tuple[3]})`
}

export const rechartsEasing = {
  entrance: toRechartsBezier(ease.entranceExpressive),
  standard: toRechartsBezier(ease.standardProductive),
}
export const rechartsDurationMs = {
  entrance: parseFloat(durationSlow01), // 400ms chart draw-in
}

// Route transitions (Shell.tsx, keyed on pathname via AnimatePresence).
export const pageTransition: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: duration.slow01, ease: ease.entranceProductive } },
  exit: { opacity: 0, y: -8, transition: { duration: duration.moderate01, ease: ease.exitProductive } },
}

// Hero KPI tiles / dashboard cards, used as the `variants` prop on a
// `motion.div` inside a `staggerContainer` parent.
export const tileEntrance: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: duration.moderate02, ease: ease.entranceProductive } },
}

// Parent wrapper: staggers `tileEntrance` children on first mount only
// (Dashboard.tsx conditionally mounts this block once real data arrives,
// so this never plays as a "loading" animation ahead of real figures).
export const staggerContainer: Variants = {
  initial: {},
  animate: { transition: { staggerChildren: 0.06, delayChildren: 0.02 } },
}

// Sidebar/topbar chrome entrance, Shell.tsx (plays once per app load).
export const shellEntrance: Variants = {
  initial: { opacity: 0, y: -8 },
  animate: { opacity: 1, y: 0, transition: { duration: duration.moderate02, ease: ease.entranceProductive } },
}

export const tileHover = {
  whileHover: { y: -2, transition: { duration: duration.fast02, ease: ease.standardProductive } },
  whileTap: { scale: 0.98, transition: { duration: duration.fast01, ease: ease.standardProductive } },
}
