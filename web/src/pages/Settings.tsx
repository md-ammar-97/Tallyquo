import { Link } from 'react-router-dom'
import { Building2, Mail, RefreshCw } from 'lucide-react'

const SETTINGS_LINKS = [
  {
    to: '/settings/profile',
    icon: Building2,
    label: 'Business profile',
    description: 'Legal identity, address, GST/HST registration, payment instructions, and invoice templates.',
  },
  {
    to: '/settings/email-accounts',
    icon: Mail,
    label: 'Email accounts',
    description: 'Connect the address invoices are sent from.',
  },
  {
    to: '/settings/recurring',
    icon: RefreshCw,
    label: 'Recurring invoices',
    description: 'Rules that auto-generate or draft invoices on a schedule.',
  },
]

export default function Settings() {
  return (
    <div>
      <h1>Settings</h1>
      <div className="settings-grid">
        {SETTINGS_LINKS.map(({ to, icon: Icon, label, description }) => (
          <Link key={to} to={to} className="settings-card">
            <Icon size={20} className="nav-icon" />
            <div>
              <strong>{label}</strong>
              <p className="caption">{description}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
