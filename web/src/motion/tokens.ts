import type { Variants } from 'motion/react'

// Static duration/easing values -- originally sourced from @carbon/motion's
// published tokens (a well-tuned, real production motion system) during the
// IBM Carbon redesign; kept as plain literals here rather than a live
// package dependency since @carbon/motion is being removed in the Wise-
// inspired redesign's cleanup phase (WI.G) and the Wise-inspired brief
// itself specifies no motion-timing system of its own to replace it with.
export const duration = {
  fast01: 0.07, // hover/press micro-feedback
  fast02: 0.11,
  moderate01: 0.15,
  moderate02: 0.24, // tile/panel entrance
  slow01: 0.4, // page transitions, count-ups, chart draw-in
  slow02: 0.7,
}

export const ease = {
  standardProductive: [0.2, 0, 0.38, 0.9] as [number, number, number, number],
  standardExpressive: [0.4, 0.14, 0.3, 1] as [number, number, number, number],
  entranceProductive: [0, 0, 0.38, 0.9] as [number, number, number, number],
  entranceExpressive: [0, 0, 0.3, 1] as [number, number, number, number],
  exitProductive: [0.2, 0, 1, 0.9] as [number, number, number, number],
  exitExpressive: [0.4, 0.14, 1, 1] as [number, number, number, number],
}

// Recharts' animationEasing prop accepts a raw CSS cubic-bezier() string,
// typed as a template literal with no spaces between numbers.
function toRechartsBezier(tuple: [number, number, number, number]): `cubic-bezier(${number},${number},${number},${number})` {
  return `cubic-bezier(${tuple[0]},${tuple[1]},${tuple[2]},${tuple[3]})`
}

export const rechartsEasing = {
  entrance: toRechartsBezier(ease.entranceExpressive),
  standard: toRechartsBezier(ease.standardProductive),
}
export const rechartsDurationMs = {
  entrance: 400, // chart draw-in
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
