import { useEffect, useState } from 'react'
import { OTPInput, type SlotProps } from 'input-otp'
import { motion, useReducedMotion, type TargetAndTransition, type Transition } from 'motion/react'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

export type OtpStatus = 'idle' | 'verifying' | 'success' | 'error'

interface OtpInputProps {
  value: string
  onChange: (value: string) => void
  length?: number
  status: OtpStatus
  disabled?: boolean
  /** Fires once the error shake has finished playing, so the caller can
      clear the code and drop status back to 'idle' for a retry. */
  onErrorAnimationComplete?: () => void
}

const BOX = 48
const GAP = 12
const STEP = BOX + GAP
const RADIUS = 74
const ORBIT_STEPS = 12

// Box i's horizontal offset from the row's centre, in its resting
// (idle) flex layout -- needed so the "move to a circle" transform is
// relative to each box's own natural position, not an absolute one.
function rowOffsetX(index: number, count: number): number {
  return (index - (count - 1) / 2) * STEP
}

// A full lap of (x, y) keyframes tracing the circle starting from box
// i's own position on it, so the whole ring keeps orbiting together
// rather than each box independently drifting. Framer Motion spaces
// keyframe arrays evenly in time by default, so ORBIT_STEPS segments of
// equal angular size produce smooth constant-speed rotation.
function orbitKeyframes(index: number, count: number) {
  const rowX = rowOffsetX(index, count)
  const base = (2 * Math.PI * index) / count - Math.PI / 2
  const xs: number[] = []
  const ys: number[] = []
  for (let s = 0; s <= ORBIT_STEPS; s++) {
    const angle = base + (2 * Math.PI * s) / ORBIT_STEPS
    xs.push(RADIUS * Math.cos(angle) - rowX)
    ys.push(RADIUS * Math.sin(angle))
  }
  return { xs, ys }
}

function Slots({
  length,
  status,
  reducedMotion,
  slots,
}: {
  length: number
  status: OtpStatus
  reducedMotion: boolean
  slots: SlotProps[]
}) {
  const [showTick, setShowTick] = useState(false)

  useEffect(() => {
    if (status !== 'success') {
      setShowTick(false)
      return
    }
    const t = setTimeout(() => setShowTick(true), reducedMotion ? 0 : 550)
    return () => clearTimeout(t)
  }, [status, reducedMotion])

  const lastIndex = length - 1

  return (
    <div className="relative flex items-center justify-center" style={{ gap: GAP, height: BOX }}>
      {Array.from({ length }).map((_, i) => {
        const slot = slots[i]
        const rowX = rowOffsetX(i, length)
        const isLast = i === lastIndex
        const { xs, ys } = orbitKeyframes(i, length)

        let animate: TargetAndTransition
        let transition: Transition = { duration: 0.3, ease: 'easeOut' }

        if (status === 'verifying') {
          animate = reducedMotion ? { x: 0, y: 0, scale: 1, opacity: 1 } : { x: xs, y: ys, scale: 1, opacity: 1 }
          transition = reducedMotion ? { duration: 0 } : { duration: 1.6, repeat: Infinity, ease: 'linear' }
        } else if (status === 'success') {
          // Every box converges on the row's centre point (x: -rowX
          // cancels each box's own offset from centre); only the last
          // one stays visible there ("one box appears"), then a tick
          // fades in on top of it once the converge has had time to land.
          animate = isLast
            ? { x: -rowX, y: 0, scale: 1, opacity: 1 }
            : { x: -rowX, y: 0, scale: 0, opacity: 0 }
          transition = { duration: reducedMotion ? 0 : 0.45, ease: 'easeIn' }
        } else if (status === 'error') {
          // Un-circle back to the row, then the same shake+flash used
          // for any invalid code -- one consistent "wrong" animation
          // regardless of what caused it.
          animate = reducedMotion
            ? { x: 0, y: 0, scale: 1, opacity: 1 }
            : { x: [xs[0], 0, -8, 8, -8, 8, 0], y: [ys[0], 0, 0, 0, 0, 0, 0], scale: 1, opacity: 1 }
          transition = { duration: reducedMotion ? 0 : 0.55, ease: 'easeOut' }
        } else {
          animate = { x: 0, y: 0, scale: 1, opacity: 1 }
        }

        return (
          <motion.div
            key={i}
            data-active={slot?.isActive}
            animate={animate}
            transition={transition}
            className={cn(
              'relative flex h-12 w-12 items-center justify-center rounded-md border border-input bg-card text-body-lg font-semibold text-ink',
              'data-[active=true]:border-ring data-[active=true]:ring-3 data-[active=true]:ring-ring/40',
              status === 'error' && 'border-destructive',
            )}
          >
            {isLast && showTick ? (
              <motion.span
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 400, damping: 18 }}
                className="text-positive-deep"
              >
                <Check className="h-6 w-6" strokeWidth={3} />
              </motion.span>
            ) : (
              slot?.char
            )}
            {slot?.hasFakeCaret && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="h-5 w-px animate-pulse bg-ink" />
              </div>
            )}
          </motion.div>
        )
      })}
    </div>
  )
}

export default function OtpInput({ value, onChange, length = 6, status, disabled, onErrorAnimationComplete }: OtpInputProps) {
  const reducedMotion = useReducedMotion() ?? false

  useEffect(() => {
    if (status !== 'error') return
    const t = setTimeout(() => onErrorAnimationComplete?.(), reducedMotion ? 0 : 600)
    return () => clearTimeout(t)
  }, [status, reducedMotion, onErrorAnimationComplete])

  return (
    <OTPInput
      value={value}
      onChange={onChange}
      maxLength={length}
      inputMode="numeric"
      pattern="^[0-9]+$"
      disabled={disabled || status === 'verifying' || status === 'success'}
      containerClassName="flex items-center justify-center"
      render={({ slots }) => <Slots length={length} status={status} reducedMotion={reducedMotion} slots={slots} />}
    />
  )
}
