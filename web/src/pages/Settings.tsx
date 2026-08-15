import { Link } from 'react-router-dom'
import { Building2, Mail, RefreshCw } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

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
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">Settings</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SETTINGS_LINKS.map(({ to, icon: Icon, label, description }) => (
          <Link key={to} to={to}>
            <Card className="h-full transition-colors hover:bg-primary-pale/40">
              <CardContent className="flex items-start gap-3">
                <Icon size={20} className="mt-0.5 shrink-0 text-ink" />
                <div>
                  <strong className="text-body-sm font-semibold text-ink">{label}</strong>
                  <p className="mt-1 text-body-sm text-mute">{description}</p>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
