import { Link } from 'react-router-dom'
import logo from '@/assets/logo.svg'

// footer component token: ink background, canvas-soft text.
export default function Footer() {
  return (
    <footer className="bg-ink px-6 py-12 text-canvas-soft md:px-12">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-8 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <img src={logo} alt="Tallyquo" className="h-7 w-auto brightness-0 invert" />
        </div>
        <p className="text-body-sm text-mute">
          &copy; {new Date().getFullYear()} Tallyquo. Invoicing and financial record-keeping for Canadian sole
          proprietors.
        </p>
        <Link to="/login" className="text-body-sm font-semibold text-primary hover:underline">
          Log in
        </Link>
      </div>
    </footer>
  )
}
