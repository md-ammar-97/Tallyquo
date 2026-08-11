import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import {
  Add,
  ChartBar,
  Dashboard as DashboardIcon,
  Document,
  Logout,
  Notification,
  Receipt,
  Settings as SettingsIcon,
  UserAvatar,
  UserMultiple,
  Help,
} from '@carbon/icons-react'
import { logout } from '../api'
import logo from '../assets/logo.svg'
import { duration, ease, pageTransition, shellEntrance } from '../motion/tokens'

const NAV_ITEMS = [
  { to: '/', end: true, label: 'Dashboard', icon: DashboardIcon },
  { to: '/invoices', label: 'Invoices', icon: Document },
  { to: '/expenses', label: 'Expenses', icon: Receipt },
  { to: '/clients', label: 'Clients', icon: UserMultiple },
  { to: '/reports', label: 'Reports', icon: ChartBar },
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
    <div className="app-shell">
      <div className="mobile-topbar">
        <span className="mobile-wordmark">Tallyquo</span>
        <button aria-label={menuOpen ? 'Close menu' : 'Open menu'} onClick={() => setMenuOpen((o) => !o)}>
          {menuOpen ? '✕' : '☰'}
        </button>
      </div>
      <motion.nav
        className={`sidebar${menuOpen ? ' open' : ''}`}
        variants={shellEntrance}
        initial="initial"
        animate="animate"
      >
        <div className="brand-block">
          <img src={logo} alt="Tallyquo" className="brand-mark" />
        </div>
        <button type="button" className="primary sidebar-cta" onClick={() => navigate('/expenses?new=1')}>
          <Add size={16} />
          Add Expense
        </button>
        <div className="sidebar-nav">
          {NAV_ITEMS.map(({ to, end, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={end} onClick={handleNavClick}>
              <Icon size={16} className="nav-icon" />
              {label}
            </NavLink>
          ))}
        </div>
        <div className="sidebar-footer">
          <button type="button" onClick={handleLogout}>
            <Logout size={16} className="nav-icon" />
            Sign out
          </button>
        </div>
      </motion.nav>
      <div className="content-column">
        <motion.div
          className="topbar"
          variants={shellEntrance}
          initial="initial"
          animate="animate"
          transition={{ duration: duration.moderate02, ease: ease.entranceProductive, delay: 0.04 }}
        >
          <h2 className="topbar-title">{pageTitle(location.pathname)}</h2>
          <div className="topbar-actions">
            <button type="button" className="primary" onClick={() => navigate('/invoices/new')}>
              Create Invoice
            </button>
            <button type="button" className="icon-button" title="Notifications (coming soon)">
              <Notification size={18} />
            </button>
            <button type="button" className="icon-button" title="Help (coming soon)">
              <Help size={18} />
            </button>
            <div className="avatar-menu">
              <button
                type="button"
                className="avatar-button"
                onClick={() => setAvatarOpen((o) => !o)}
                aria-label="Account menu"
              >
                <UserAvatar size={16} />
              </button>
              {avatarOpen && (
                <div className="avatar-dropdown">
                  <button type="button" onClick={handleLogout}>
                    <Logout size={14} className="nav-icon" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </motion.div>
        <div className="main">
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
