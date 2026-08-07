import { Link } from 'react-router-dom'

export default function Dashboard() {
  return (
    <div>
      <h1>Dashboard</h1>
      <div className="block">
        <div className="block-body">
          <p style={{ marginBottom: 16 }}>
            Phase 1: correct invoices, nothing else. Set up your business profile and a client, then issue a
            correctly-taxed invoice in under two minutes.
          </p>
          <Link to="/profile">
            <button>1. Business profile</button>
          </Link>{' '}
          <Link to="/clients">
            <button>2. Add a client</button>
          </Link>{' '}
          <Link to="/invoices/new">
            <button className="primary">3. Issue an invoice</button>
          </Link>
        </div>
      </div>
    </div>
  )
}
