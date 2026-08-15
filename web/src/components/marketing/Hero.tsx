import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import ProductMockup from './ProductMockup'

// hero-band component token: sage canvas, display-mega headline (Manrope
// 900). Split layout at desktop (headline left, mockup right), stacked
// below 768px per the brief's own breakpoint table.
export default function Hero() {
  return (
    <section className="bg-background px-6 py-16 md:px-12 md:py-24">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-12 md:flex-row md:items-center md:justify-between">
        <div className="flex max-w-xl flex-col items-start gap-6 text-left">
          <span className="rounded-pill bg-primary-pale px-4 py-1.5 text-body-sm font-semibold text-positive-deep">
            Built for Canadian sole proprietors
          </span>
          <h1 className="font-display text-display-lg text-ink md:text-display-xl">
            Know exactly what&apos;s yours to spend.
          </h1>
          <p className="text-body-lg text-body">
            Tallyquo issues correctly-taxed invoices, tracks every expense and receipt, and tells you what to set
            aside for income tax, CPP, and GST/HST &mdash; before your accountant has to ask.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button asChild size="lg" className="h-12 px-6 text-button-md">
              <Link to="/login">Get started free</Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-12 px-6 text-button-md">
              <Link to="/login">Log in</Link>
            </Button>
          </div>
          <p className="text-caption text-mute">No credit card. Sign in with just your email.</p>
        </div>

        <ProductMockup />
      </div>
    </section>
  )
}
