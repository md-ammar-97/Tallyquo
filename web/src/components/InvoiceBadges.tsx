import { Badge } from '@/components/ui/badge'

// paid is the one status that's a genuine positive outcome (design.md's
// colour-polarity rule) -- shadcn's default Badge variant is brand lime,
// which stays reserved for the CTA identity, so paid gets a positive-tint
// override rather than the default variant. (overdue's contrast is fixed
// at the badge.tsx variant level -- WI.G.)
export function InvoiceStatusBadge({ status }: { status: string }) {
  return (
    <Badge
      variant={status === 'overdue' ? 'destructive' : 'secondary'}
      className={`capitalize ${status === 'paid' ? 'bg-positive/15 text-positive-deep' : ''}`}
    >
      {status.replace(/_/g, ' ')}
    </Badge>
  )
}

export function TaxTreatmentBadge({ treatment }: { treatment: string }) {
  return (
    <Badge variant="secondary" className="capitalize">
      {treatment.replace(/_/g, ' ')}
    </Badge>
  )
}
