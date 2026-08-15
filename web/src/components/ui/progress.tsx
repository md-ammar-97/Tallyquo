import * as React from "react"
import { Progress as ProgressPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function Progress({
  className,
  value,
  ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root>) {
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      className={cn(
        "relative flex h-1 w-full items-center overflow-x-hidden rounded-full bg-muted",
        className
      )}
      {...props}
    >
      {/* bg-positive-deep, not bg-primary: lime is reserved for the CTA
          identity (never repurposed as a status colour, design.md), and
          WI.G's contrast re-check found lime fails the 3:1 non-text
          threshold against the muted track regardless (1.29:1) -- every
          light, high-luminance fill does, it's not track-color-specific.
          positive-deep reads as "on track" and clears it at 8.76:1. */}
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className="size-full flex-1 bg-positive-deep transition-all"
        style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  )
}

export { Progress }
