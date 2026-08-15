import { Check } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

// design.md's Compliance Checklist: "a vertical stepper used during
// invoice creation. Incomplete items use Text-muted; completed items
// use Compliance Green checkmarks." Deliberately advisory-only -- this
// never blocks anything itself. POST /invoices/:id/issue's server-side
// ComplianceError (invoices_service.issue_invoice) remains the sole
// enforcement; a rule not mirrored here (e.g. due date before invoice
// date) still correctly blocks issuance even if every item below shows
// complete.

export interface ComplianceProfile {
  legal_name: string | null
  registration_status: string
  gst_hst_number: string | null
}

export interface ComplianceClient {
  address_line1: string | null
  city: string | null
}

interface Props {
  profile: ComplianceProfile | null
  client: ComplianceClient | null
  taxReady: boolean
}

interface Item {
  label: string
  done: boolean
  detail: string
}

export default function ComplianceChecklist({ profile, client, taxReady }: Props) {
  const bnRequired = profile?.registration_status === 'registered'
  const items: Item[] = [
    {
      label: 'Business name',
      done: !!profile?.legal_name,
      detail: profile?.legal_name || 'Add your legal business name in Business profile.',
    },
    {
      label: 'BN number',
      done: !bnRequired || !!profile?.gst_hst_number,
      detail: bnRequired
        ? profile?.gst_hst_number || 'Registered for GST/HST but no BN on file yet.'
        : 'Not required -- not registered for GST/HST.',
    },
    {
      label: 'Client address',
      done: !!client?.address_line1 && !!client?.city,
      detail: client?.address_line1 && client?.city ? 'On file.' : 'Add an address for this client.',
    },
    {
      label: 'Tax breakdown',
      done: taxReady,
      detail: taxReady ? 'Calculated.' : 'Pending tax selection.',
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-display text-display-xs font-semibold text-ink">Compliance checklist</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-3">
          {items.map((item) => (
            <li key={item.label} className="flex items-start gap-3">
              <span
                className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full ${
                  item.done ? 'bg-positive text-canvas' : 'border border-divider'
                }`}
              >
                {item.done ? <Check size={13} /> : null}
              </span>
              <span>
                <strong className="text-body-sm font-semibold text-ink">{item.label}</strong>
                <div className="text-caption text-mute">{item.detail}</div>
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
