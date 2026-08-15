import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import logo from '@/assets/logo.svg'

// docs/screens/DESIGN (2).md's nav-bar component token: canvas background,
// ink text, body-sm-strong nav links. Both CTAs point at the same /login
// route -- the existing email-OTP flow already handles first-time and
// returning users identically ("Signing in creates one automatically"),
// so there's no separate signup form to build.
export default function NavBar() {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between bg-card px-6 py-4 md:px-12">
      <Link to="/" className="flex items-center gap-2">
        <img src={logo} alt="Tallyquo" className="h-11 w-auto" />
      </Link>
      <nav className="flex items-center gap-3">
        <Button asChild variant="ghost">
          <Link to="/login">Log in</Link>
        </Button>
        <Button asChild>
          <Link to="/login">Sign up free</Link>
        </Button>
      </nav>
    </header>
  )
}
