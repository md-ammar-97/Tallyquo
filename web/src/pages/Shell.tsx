import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import {
  Plus,
  BarChart3,
  LayoutDashboard as DashboardIcon,
  FileText,
  LogOut,
  Bell,
  Receipt,
  Settings as SettingsIcon,
  CircleUser,
  Users,
  HelpCircle,
  Menu,
  X,
} from 'lucide-react'
import { logout } from '../api'
import logo from '../assets/logo.svg'
import { duration, ease, pageTransition, shellEntrance } from '../motion/tokens'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const NAV_ITEMS = [
  { to: '/', end: true, label: 'Dashboard', icon: DashboardIcon },
  { to: '/invoices', label: 'Invoices', icon: FileText },
  { to: '/expenses', label: 'Expenses', icon: Receipt },
  { to: '/clients', label: 'Clients', icon: Users },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

// Topbar page title -- matched against the longest prefix so nested
// routes (e.g. /clients/:id) still resolve to their parent's label.
const PAGE_TITLES: { prefix: string; title: string }[] = [
  { prefix: '/invoices/new', title: 'New invoice' },
  { prefix: '/invoices', title: 'Invoices' },
  { prefix: '/expenses', title: 'Expenses' },
  { prefix: '/clients', title: 'Clients' },
  { prefix: '/reports', title: 'Reports' },
  { prefix: '/settings/profile', title: 'Business profile' },
  { prefix: '/settings/email-accounts', title: 'Email accounts' },
  { prefix: '/settings/recurring', title: 'Recurring' },
  { prefix: '/settings/templates', title: 'Invoice template' },
  { prefix: '/settings', title: 'Settings' },
  { prefix: '/', title: 'Dashboard' },
]

function pageTitle(pathname: string): string {
  const match = PAGE_TITLES.filter((p) => pathname.startsWith(p.prefix)).sort(
    (a, b) => b.prefix.length - a.prefix.length,
  )[0]
  return match?.title ?? 'Tallyquo'
}

export default function Shell() {
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [avatarOpen, setAvatarOpen] = useState(false)

  function handleLogout() {
    logout()
    navigate('/login')
  }

  function handleNavClick() {
    setMenuOpen(false)
  }

  return (
    <div className="flex min-h-screen bg-background font-sans">
      {/* Mobile topbar: hamburger toggle only, real topbar lives below */}
      <div className="fixed inset-x-0 top-0 z-30 flex items-center justify-between border-b border-divider bg-card px-4 py-3 md:hidden">
        <span className="font-display text-display-xs text-ink">Tallyquo</span>
        <button
          type="button"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          onClick={() => setMenuOpen((o) => !o)}
          className="flex h-9 w-9 items-center justify-center rounded-md text-ink"
        >
          {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>
      {menuOpen && (
        <div className="fixed inset-0 z-30 bg-ink/40 md:hidden" onClick={() => setMenuOpen(false)} />
      )}

      <motion.nav
        variants={shellEntrance}
        initial="initial"
        animate="animate"
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col gap-6 border-r border-divider bg-card p-5 transition-transform md:sticky md:top-0 md:h-screen md:translate-x-0',
          menuOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between">
          <img src={logo} alt="Tallyquo" className="h-10 w-auto" />
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setMenuOpen(false)}
            className="flex h-8 w-8 items-center justify-center rounded-md text-mute md:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <Button className="h-11 w-full text-button-md" onClick={() => navigate('/expenses?new=1')}>
          <Plus className="h-4 w-4" />
          Add expense
        </Button>

        <div className="flex flex-1 flex-col gap-1">
          {NAV_ITEMS.map(({ to, end, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={handleNavClick}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2.5 text-body-sm font-semibold text-ink transition-colors',
                  isActive ? 'bg-primary-pale text-positive-deep' : 'hover:bg-canvas-soft',
                )
              }
            >
              <Icon className="h-[18px] w-[18px]" />
              {label}
            </NavLink>
          ))}
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="flex items-center gap-3 rounded-md px-3 py-2.5 text-body-sm font-semibold text-mute transition-colors hover:bg-canvas-soft hover:text-negative"
        >
          <LogOut className="h-[18px] w-[18px]" />
          Sign out
        </button>
      </motion.nav>

      <div className="flex min-w-0 flex-1 flex-col pt-[57px] md:pt-0">
        <motion.div
          variants={shellEntrance}
          initial="initial"
          animate="animate"
          transition={{ duration: duration.moderate02, ease: ease.entranceProductive, delay: 0.04 }}
          className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-divider bg-card px-6"
        >
          <h2 className="font-display text-display-xs text-ink">{pageTitle(location.pathname)}</h2>
          <div className="flex items-center gap-2">
            <Button className="h-10 text-button-md" onClick={() => navigate('/invoices/new')}>
              Create invoice
            </Button>
            <button
              type="button"
              title="Notifications (coming soon)"
              className="flex h-10 w-10 items-center justify-center rounded-md text-mute transition-colors hover:bg-canvas-soft hover:text-ink"
            >
              <Bell className="h-[18px] w-[18px]" />
            </button>
            <button
              type="button"
              title="Help (coming soon)"
              className="flex h-10 w-10 items-center justify-center rounded-md text-mute transition-colors hover:bg-canvas-soft hover:text-ink"
            >
              <HelpCircle className="h-[18px] w-[18px]" />
            </button>
            <div className="relative">
              <button
                type="button"
                onClick={() => setAvatarOpen((o) => !o)}
                aria-label="Account menu"
                className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-ink"
              >
                <CircleUser className="h-5 w-5" />
              </button>
              {avatarOpen && (
                <div className="absolute right-0 top-12 z-30 min-w-[160px] rounded-md border border-divider bg-card p-1 shadow-[0_12px_32px_-12px_rgba(14,15,12,0.25)]">
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-body-sm font-semibold text-ink hover:bg-canvas-soft"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </motion.div>
        <div className="flex-1 p-6">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={location.pathname} variants={pageTransition} initial="initial" animate="animate" exit="exit">
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
