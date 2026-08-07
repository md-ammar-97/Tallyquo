import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { logout } from '../api'

export default function Shell() {
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <nav className="sidebar">
        <div style={{ fontWeight: 600, padding: '0 12px', marginBottom: 16 }}>Tallyquo</div>
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        <NavLink to="/invoices">Invoices</NavLink>
        <NavLink to="/expenses">Expenses</NavLink>
        <NavLink to="/clients">Clients</NavLink>
        <NavLink to="/profile">Business profile</NavLink>
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
