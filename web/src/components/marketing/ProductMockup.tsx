// The hero's product mockup -- decision #1: a real (if stylized) preview
// of the Dashboard rather than the attached AI-parsing graphic (whose own
// messaging describes a different product) or a plain illustration. Built
// from real UI primitives at a fixed size rather than an external
// screenshot asset, which this app doesn't have -- the brief's own
// "Image Behavior" section explicitly prefers "product mockups inside
// cards" over illustrative art.
export default function ProductMockup() {
  return (
    <div className="w-full max-w-md overflow-hidden rounded-xl bg-card ring-1 ring-ink/10 shadow-[0_24px_60px_-24px_rgba(14,15,12,0.35)]">
      {/* faux browser chrome */}
      <div className="flex items-center gap-1.5 border-b border-divider bg-canvas-soft px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-negative/60" />
        <span className="h-2.5 w-2.5 rounded-full bg-warning/60" />
        <span className="h-2.5 w-2.5 rounded-full bg-positive/60" />
        <span className="ml-2 text-caption text-mute">tallyquo.app</span>
      </div>

      <div className="flex flex-col gap-4 p-5">
        <div>
          <p className="text-caption text-mute">Year-to-date projection</p>
          <p className="font-display text-display-xs text-ink">How much is mine?</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-md bg-canvas-soft p-3">
            <p className="text-caption text-mute">Revenue</p>
            <p className="text-body-lg font-semibold text-ink">CAD 84,200</p>
          </div>
          <div className="rounded-md bg-primary-pale p-3">
            <p className="text-caption text-positive-deep">Safe to spend</p>
            <p className="text-body-lg font-semibold text-positive-deep">CAD 51,900</p>
          </div>
        </div>

        <div className="rounded-md bg-canvas-soft p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-caption text-mute">GST/HST held for CRA</p>
            <p className="text-caption text-mute">Q3</p>
          </div>
          <div className="flex h-16 items-end gap-1.5">
            {[40, 65, 50, 80, 60, 90, 70].map((h, i) => (
              <span
                key={i}
                className="flex-1 rounded-t-sm bg-primary"
                style={{ height: `${h}%`, opacity: 0.55 + i * 0.06 }}
              />
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between rounded-md border border-divider px-3 py-2.5">
          <div>
            <p className="text-body-sm font-semibold text-ink">Invoice INV-2026-014</p>
            <p className="text-caption text-mute">Northwind Studio &middot; Issued</p>
          </div>
          <span className="rounded-pill bg-primary-pale px-3 py-1 text-caption font-semibold text-positive-deep">
            Paid
          </span>
        </div>
      </div>
    </div>
  )
}
