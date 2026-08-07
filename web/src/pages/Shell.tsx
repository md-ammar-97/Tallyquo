import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { logout } from '../api'

export default function Shell() {
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

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
        <span style={{ fontWeight: 600 }}>Tallyquo</span>
        <button aria-label={menuOpen ? 'Close menu' : 'Open menu'} onClick={() => setMenuOpen((o) => !o)}>
          {menuOpen ? '✕' : '☰'}
        </button>
      </div>
      <nav className={`sidebar${menuOpen ? ' open' : ''}`}>
        <div style={{ fontWeight: 600, padding: '0 12px', marginBottom: 16 }}>Tallyquo</div>
        <NavLink to="/" end onClick={handleNavClick}>
          Dashboard
        </NavLink>
        <NavLink to="/invoices" onClick={handleNavClick}>
          Invoices
        </NavLink>
        <NavLink to="/expenses" onClick={handleNavClick}>
          Expenses
        </NavLink>
        <NavLink to="/recurring" onClick={handleNavClick}>
          Recurring
        </NavLink>
        <NavLink to="/clients" onClick={handleNavClick}>
          Clients
        </NavLink>
        <NavLink to="/profile" onClick={handleNavClick}>
          Business profile
        </NavLink>
        <div style={{ marginTop: 24 }}>
          <button onClick={handleLogout} style={{ width: '100%' }}>
            Sign out
          </button>
        </div>
      </nav>
      <div className="main">
        <Outlet />
      </div>
    </div>
  )
}
