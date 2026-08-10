import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Bell,
  Building2,
  FileText,
  HelpCircle,
  LayoutDashboard,
  LogOut,
  Mail,
  Plus,
  Receipt,
  Repeat,
  User,
  Users,
} from 'lucide-react'
import { logout } from '../api'
import logo from '../assets/logo.svg'

const NAV_ITEMS = [
  { to: '/', end: true, label: 'Dashboard', icon: LayoutDashboard },
  { to: '/invoices', label: 'Invoices', icon: FileText },
  { to: '/expenses', label: 'Expenses', icon: Receipt },
  { to: '/recurring', label: 'Recurring', icon: Repeat },
  { to: '/clients', label: 'Clients', icon: Users },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/profile', label: 'Business profile', icon: Building2 },
  { to: '/email-accounts', label: 'Email accounts', icon: Mail },
]

// Topbar page title -- matched against the longest prefix so nested
// routes (e.g. /clients/:id) still resolve to their parent's label.
const PAGE_TITLES: { prefix: string; title: string }[] = [
  { prefix: '/invoices/new', title: 'New invoice' },
  { prefix: '/invoices', title: 'Invoices' },
  { prefix: '/expenses', title: 'Expenses' },
  { prefix: '/recurring', title: 'Recurring' },
  { prefix: '/clients', title: 'Clients' },
  { prefix: '/reports', title: 'Reports' },
  { prefix: '/profile', title: 'Business profile' },
  { prefix: '/email-accounts', title: 'Email accounts' },
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
      <nav className={`sidebar${menuOpen ? ' open' : ''}`}>
        <div className="brand-block">
          <img src={logo} alt="Tallyquo" className="brand-mark" />
        </div>
        <button type="button" className="primary sidebar-cta" onClick={() => navigate('/expenses?new=1')}>
          <Plus size={16} />
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
            <LogOut size={16} className="nav-icon" />
            Sign out
          </button>
        </div>
      </nav>
      <div className="content-column">
        <div className="topbar">
          <h2 className="topbar-title">{pageTitle(location.pathname)}</h2>
          <div className="topbar-actions">
            <button type="button" className="primary" onClick={() => navigate('/invoices/new')}>
              Create Invoice
            </button>
            <button type="button" className="icon-button" title="Notifications (coming soon)">
              <Bell size={18} />
            </button>
            <button type="button" className="icon-button" title="Help (coming soon)">
              <HelpCircle size={18} />
            </button>
            <div className="avatar-menu">
              <button
                type="button"
                className="avatar-button"
                onClick={() => setAvatarOpen((o) => !o)}
                aria-label="Account menu"
              >
                <User size={16} />
              </button>
              {avatarOpen && (
                <div className="avatar-dropdown">
                  <button type="button" onClick={handleLogout}>
                    <LogOut size={14} className="nav-icon" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="main">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
