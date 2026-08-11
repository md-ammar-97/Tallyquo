import { Checkmark } from '@carbon/icons-react'

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
    <div className="block">
      <div className="block-header">
        <h2>Compliance checklist</h2>
      </div>
      <div className="block-body">
        <ul className="compliance-checklist">
          {items.map((item) => (
            <li key={item.label} className={item.done ? 'done' : ''}>
              <span className="compliance-checklist-icon">
                {item.done ? <Checkmark size={14} /> : <span className="compliance-checklist-dot" />}
              </span>
              <span>
                <strong>{item.label}</strong>
                <div className="caption">{item.detail}</div>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
