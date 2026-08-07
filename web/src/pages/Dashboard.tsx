import { useState } from 'react'
import { Link } from 'react-router-dom'
import { downloadFile } from '../api'

export default function Dashboard() {
  const [pnlGroupBy, setPnlGroupBy] = useState('month')

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="block">
        <div className="block-body">
          <p style={{ marginBottom: 16 }}>
            Set up your business profile and a client, then issue a correctly-taxed invoice in under two minutes.
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

      <div className="block">
        <div className="block-header">
          <h2>Reports</h2>
        </div>
        <div className="block-body" style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>P&amp;L grouped by</label>
            <select value={pnlGroupBy} onChange={(e) => setPnlGroupBy(e.target.value)}>
              <option value="month">Month</option>
              <option value="quarter">Quarter</option>
              <option value="year">Year</option>
            </select>
          </div>
          <button onClick={() => downloadFile(`/reports/pnl.csv?group_by=${pnlGroupBy}`, 'pnl.csv')}>
            Download P&amp;L CSV
          </button>
        </div>
      </div>
    </div>
  )
}
