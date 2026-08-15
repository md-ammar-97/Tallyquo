import { Calculator, FileCheck2, PiggyBank, Receipt } from 'lucide-react'
import type { ComponentType } from 'react'

interface Feature {
  icon: ComponentType<{ className?: string }>
  title: string
  body: string
  tint: 'sage' | 'green' | 'dark'
}

// Real product capabilities, not the attached AI-parsing graphic's
// generic document-comprehension framing -- see decision #1. Card tint
// varies per the brief's own "Do" guidance (card-feature-sage/-green/
// -dark).
const FEATURES: Feature[] = [
  {
    icon: FileCheck2,
    title: 'Correct tax, every invoice',
    body: 'GST/HST/PST calculated for the right jurisdiction automatically, including zero-rated exports and non-residency evidence -- not a rate you have to remember.',
    tint: 'sage',
  },
  {
    icon: Receipt,
    title: 'Expenses without the spreadsheet',
    body: 'Drop in a receipt and Tallyquo pulls the vendor, date, and amount, sorted into the right CRA line automatically.',
    tint: 'green',
  },
  {
    icon: PiggyBank,
    title: 'Know what to set aside',
    body: 'A running estimate of income tax, CPP, and GST/HST owing -- so a good month never turns into a surprise bill in April.',
    tint: 'dark',
  },
  {
    icon: Calculator,
    title: 'Ready for your accountant',
    body: 'A one-click year-end pack: every invoice, every receipt, and a GST/HST summary, bundled and ready to hand off.',
    tint: 'sage',
  },
]

const TINT_CLASSES: Record<Feature['tint'], string> = {
  sage: 'bg-canvas-soft text-ink',
  green: 'bg-primary-pale text-ink',
  dark: 'bg-ink text-primary',
}

export default function FeatureGrid() {
  return (
    <section className="bg-card px-6 py-16 md:px-12 md:py-24">
      <div className="mx-auto max-w-6xl">
        <h2 className="font-display text-display-md text-ink">Everything the invoice needs to be right the first time.</h2>
        <div className="mt-10 grid gap-5 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, body, tint }) => (
            <div key={title} className={`rounded-xl p-6 ${TINT_CLASSES[tint]}`}>
              <Icon className="h-8 w-8" />
              <h3 className="mt-4 text-display-xs font-semibold">{title}</h3>
              <p className={`mt-2 text-body-md ${tint === 'dark' ? 'text-primary-neutral' : 'text-body'}`}>{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
