// The invoice document as a web-rendered preview (design.md's own
// principle: "a separate design system from the app, sharing only
// tokens -- a printed business document, not a web page"). Matches
// docs/screens/sample_innovice.png's layout. Purely presentational --
// fed by GET /invoices/:id/document, GET /public/invoices/:token/document,
// or POST /invoices/preview-document, all of which return the same
// shape from the backend's assemble_invoice_document/
// assemble_preview_document (api/src/tallyquo/billing/invoices_service.py).

export interface DocumentLineItem {
  description: string
  quantity: string
  unit: string
  unit_rate: string
  amount: string
}

export interface DocumentTaxLine {
  label: string
  rate: string | null
  amount: string
  display_note: string | null
}

export interface InvoiceDocumentData {
  invoice: {
    number: string | null
    invoice_date: string | null
    due_date: string | null
    service_period_start: string | null
    service_period_end: string | null
    currency: string
    po_reference: string | null
    notes: string | null
    subtotal: string
    tax_total: string
    total: string
    line_items: DocumentLineItem[]
    tax_lines: DocumentTaxLine[]
  }
  supplier: {
    legal_name: string
    operating_name: string | null
    address_line1: string | null
    address_line2: string | null
    city: string | null
    region_code: string | null
    postal_code: string | null
    country_code: string | null
    email: string | null
    gst_hst_number: string | null
  }
  client: {
    legal_name: string
    address_line1: string | null
    address_line2: string | null
    city: string | null
    region_code: string | null
    postal_code: string | null
    country_code: string | null
  }
  payment_instruction: {
    label: string | null
    method: string | null
    provider: string | null
    account_holder: string | null
    currency: string | null
    fields: Record<string, string>
  } | null
  notes_visible: boolean
}

function addressLines(entity: {
  address_line1: string | null
  address_line2: string | null
  city: string | null
  region_code: string | null
  postal_code: string | null
  country_code?: string | null
}): string[] {
  return [
    entity.address_line1,
    entity.address_line2,
    [entity.city, entity.region_code, entity.postal_code].filter(Boolean).join(', '),
    entity.country_code,
  ].filter((l): l is string => !!l)
}

export default function InvoiceDocument({ data }: { data: InvoiceDocumentData }) {
  const { invoice, supplier, client, payment_instruction: payment } = data

  return (
    <div className="invoice-document">
      <div className="invoice-document-header">
        <div>
          <div className="invoice-document-title">INVOICE</div>
          <dl className="invoice-document-meta">
            <div>
              <dt>Invoice date</dt>
              <dd>{invoice.invoice_date ?? '—'}</dd>
            </div>
            <div>
              <dt>Invoice number</dt>
              <dd>{invoice.number ?? '(draft)'}</dd>
            </div>
            <div>
              <dt>Due date</dt>
              <dd>{invoice.due_date ?? '—'}</dd>
            </div>
            <div>
              <dt>Currency</dt>
              <dd>{invoice.currency}</dd>
            </div>
          </dl>
        </div>
        <div className="invoice-document-supplier">
          <strong>{supplier.operating_name || supplier.legal_name}</strong>
          {supplier.operating_name && <div>{supplier.legal_name}, sole proprietor</div>}
          {addressLines(supplier).map((line, i) => (
            <div key={i}>{line}</div>
          ))}
          {supplier.gst_hst_number && <div className="caption">GST/HST BN: {supplier.gst_hst_number}</div>}
        </div>
      </div>

      <div className="invoice-document-billto">
        <div className="caption">Billed to</div>
        <strong>{client.legal_name}</strong>
        {addressLines(client).map((line, i) => (
          <div key={i}>{line}</div>
        ))}
      </div>

      <table className="invoice-document-lines">
        <thead>
          <tr>
            <th>Description</th>
            <th>Qty</th>
            <th>Rate</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {invoice.line_items.map((li, i) => (
            <tr key={i}>
              <td>{li.description}</td>
              <td className="amount">{li.quantity}</td>
              <td className="amount">
                {invoice.currency} {li.unit_rate}
              </td>
              <td className="amount">
                {invoice.currency} {li.amount}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="invoice-document-totals">
        <table>
          <tbody>
            <tr>
              <td>Subtotal</td>
              <td className="amount">
                {invoice.currency} {invoice.subtotal}
              </td>
            </tr>
            {invoice.tax_lines.map((tl, i) => (
              <tr key={i}>
                <td>{tl.display_note ? `GST/HST: ${tl.display_note}` : tl.label}</td>
                <td className="amount">{tl.display_note ? '' : `${invoice.currency} ${tl.amount}`}</td>
              </tr>
            ))}
            <tr className="invoice-document-total-due">
              <td>Total due</td>
              <td className="amount">
                {invoice.currency} {invoice.total}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {payment && (
        <div className="invoice-document-payment">
          <div className="caption">Payment instructions ({payment.currency})</div>
          {payment.method && <div>{payment.method.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())}</div>}
          {payment.provider && <div>{payment.provider}</div>}
          {payment.account_holder && <div>Account holder: {payment.account_holder}</div>}
          {Object.entries(payment.fields || {}).map(([k, v]) =>
            v ? (
              <div key={k}>
                {k.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())}: {v}
              </div>
            ) : null,
          )}
        </div>
      )}

      {data.notes_visible && invoice.notes && (
        <div className="invoice-document-notes">
          <div className="caption">Notes</div>
          <div>{invoice.notes}</div>
        </div>
      )}
    </div>
  )
}
