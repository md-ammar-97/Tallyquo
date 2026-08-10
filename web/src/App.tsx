import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { isAuthenticated } from './api'
import Login from './pages/Login'
import Shell from './pages/Shell'
import Dashboard from './pages/Dashboard'
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

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/share/:token" element={<PublicInvoice />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Shell />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="profile" element={<Profile />} />
          <Route path="clients" element={<Clients />} />
          <Route path="clients/:id" element={<ClientDetail />} />
          <Route path="invoices" element={<Ledger />} />
          <Route path="invoices/new" element={<InvoiceBuilder />} />
          <Route path="invoices/:id" element={<InvoiceDetail />} />
          <Route path="expenses" element={<Expenses />} />
          <Route path="recurring" element={<Recurring />} />
          <Route path="email-accounts" element={<EmailAccounts />} />
          <Route path="reports" element={<Reports />} />
          <Route path="templates/new" element={<TemplateEditor />} />
          <Route path="templates/:id/edit" element={<TemplateEditor />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
