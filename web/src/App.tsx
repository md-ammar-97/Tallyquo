import { Navigate, Route, BrowserRouter, Routes, useLocation } from 'react-router-dom'
import { isAuthenticated } from './api'
import Login from './pages/Login'
import Home from './pages/Home'
import Shell from './pages/Shell'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import Profile from './pages/Profile'
import Clients from './pages/Clients'
import ClientDetail from './pages/ClientDetail'
import EmailAccounts from './pages/EmailAccounts'
import Expenses from './pages/Expenses'
import InvoiceBuilder from './pages/InvoiceBuilder'
import InvoiceDetail from './pages/InvoiceDetail'
import Ledger from './pages/Ledger'
import PublicInvoice from './pages/PublicInvoice'
import Recurring from './pages/Recurring'
import Reports from './pages/Reports'
import TemplateEditor from './pages/TemplateEditor'

// Owns the one literal "/" route -- React Router can't branch on two
// sibling routes matching the same path, so the auth/homepage decision
// has to live inside whichever element owns "/". useLocation().pathname
// reflects the real browser URL, so `=== '/'` correctly distinguishes
// the bare root from every nested authenticated route sharing this same
// parent element tree (/clients, /invoices/new, etc). isAuthenticated()
// reads a synchronous, already-populated value (api.ts's module-level
// accessToken, seeded from localStorage at import time) so there's no
// flash-of-homepage for an already-logged-in visitor -- the authenticated
// branch renders Shell unconditionally, Home never mounts at all.
function RootGate() {
  const location = useLocation()
  if (isAuthenticated()) return <Shell />
  if (location.pathname === '/') return <Home />
  return <Navigate to="/login" replace />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/share/:token" element={<PublicInvoice />} />
        <Route path="/" element={<RootGate />}>
          <Route index element={<Dashboard />} />
          <Route path="clients" element={<Clients />} />
          <Route path="clients/:id" element={<ClientDetail />} />
          <Route path="invoices" element={<Ledger />} />
          <Route path="invoices/new" element={<InvoiceBuilder />} />
          <Route path="invoices/:id" element={<InvoiceDetail />} />
          <Route path="expenses" element={<Expenses />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
          <Route path="settings/profile" element={<Profile />} />
          <Route path="settings/email-accounts" element={<EmailAccounts />} />
          <Route path="settings/recurring" element={<Recurring />} />
          <Route path="settings/templates/new" element={<TemplateEditor />} />
          <Route path="settings/templates/:id/edit" element={<TemplateEditor />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
