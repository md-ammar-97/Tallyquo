from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator

SUPPORTED_CURRENCIES = {"CAD", "USD"}


class InvoiceLineIn(BaseModel):
    description: str
    quantity: Decimal = Decimal("1")
    unit: str = "fixed"
    unit_rate: Decimal
    amount: Decimal
    is_taxable: bool = True
    project_ref: str | None = None


class InvoiceDraftIn(BaseModel):
    client_id: UUID
    project_id: UUID | None = None
    invoice_date: date | None = None
    service_period_start: date | None = None
    service_period_end: date | None = None
    payment_terms_days: int | None = None
    due_date: date | None = None
    currency: str = "CAD"
    po_reference: str | None = None
    description: str | None = None
    notes: str | None = None
    footer_text: str | None = None
    template_id: UUID | None = None
    include_provincial_sales_tax: bool = False
    line_items: list[InvoiceLineIn] = []

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"currency must be one of {sorted(SUPPORTED_CURRENCIES)}")
        return v


class InvoiceLineOut(InvoiceLineIn):
    id: UUID

    model_config = {"from_attributes": True}


class InvoiceTaxLineOut(BaseModel):
    tax_type: str | None
    label: str
    rate: Decimal | None
    taxable_base: Decimal
    amount: Decimal
    display_note: str | None

    model_config = {"from_attributes": True}


class InvoiceOut(BaseModel):
    id: UUID
    client_id: UUID
    number: str | None
    status: str
    invoice_date: date | None
    service_period_start: date | None
    service_period_end: date | None
    due_date: date | None
    currency: str
    subtotal: Decimal
    discount_amount: Decimal
    tax_total: Decimal
    total: Decimal
    amount_paid: Decimal
    tax_treatment_snapshot: str | None
    tax_jurisdiction_snapshot: str | None
    po_reference: str | None
    notes: str | None
    created_at: datetime
    issued_at: datetime | None
    cancelled_at: datetime | None
    revision: int
    parent_invoice_id: UUID | None
    total_cad: Decimal | None
    fx_rate_to_cad: Decimal | None
    fx_rate_date: date | None
    fx_rate_source: str | None
    has_share_link: bool
    client_name: str | None = None
    line_items: list[InvoiceLineOut] = []
    tax_lines: list[InvoiceTaxLineOut] = []

    model_config = {"from_attributes": True}


class InvoiceDocumentInvoiceOut(BaseModel):
    """The web-rendered document preview's `invoice` sub-object (GET
    /invoices/:id/document, POST /invoices/preview-document). Deliberately
    NOT InvoiceOut -- a pre-issue preview has no id/status/created_at at
    all, so this is the smaller subset both the real-invoice and
    ad-hoc-draft assemblers actually produce. line_items uses
    InvoiceLineIn (no `id` required) for the same reason: a preview's
    lines are echoed straight back from the request body."""

    number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    service_period_start: date | None = None
    service_period_end: date | None = None
    currency: str
    po_reference: str | None = None
    notes: str | None = None
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    line_items: list[InvoiceLineIn] = []
    tax_lines: list[InvoiceTaxLineOut] = []


class InvoiceDocumentSupplierOut(BaseModel):
    legal_name: str
    operating_name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region_code: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    email: str | None = None
    gst_hst_number: str | None = None


class InvoiceDocumentClientOut(BaseModel):
    legal_name: str
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region_code: str | None = None
    postal_code: str | None = None
    country_code: str | None = None


class InvoiceDocumentPaymentInstructionOut(BaseModel):
    label: str | None = None
    method: str | None = None
    provider: str | None = None
    account_holder: str | None = None
    currency: str | None = None
    fields: dict[str, str] = {}


class InvoiceDocumentOut(BaseModel):
    invoice: InvoiceDocumentInvoiceOut
    supplier: InvoiceDocumentSupplierOut
    client: InvoiceDocumentClientOut
    payment_instruction: InvoiceDocumentPaymentInstructionOut | None = None
    notes_visible: bool


class PreviewDocumentIn(BaseModel):
    client_id: UUID
    invoice_date: date | None = None
    due_date: date | None = None
    service_period_start: date | None = None
    service_period_end: date | None = None
    currency: str = "CAD"
    po_reference: str | None = None
    notes: str | None = None
    include_provincial_sales_tax: bool = False
    line_items: list[InvoiceLineIn] = []


class IssueInvoiceIn(BaseModel):
    confirm_zero_total: bool = False


class CreditNoteIn(BaseModel):
    amount: Decimal
    tax_amount: Decimal = Decimal("0")
    reason: str


class PaymentIn(BaseModel):
    amount: Decimal
    received_date: date
    method: str | None = None
    reference: str | None = None
    note: str | None = None


class PaymentOut(BaseModel):
    id: UUID
    invoice_id: UUID
    amount: Decimal
    currency: str
    amount_cad: Decimal | None
    fx_rate_to_cad: Decimal | None
    fx_gain_loss: Decimal | None
    received_date: date
    method: str | None
    reference: str | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditNoteOut(BaseModel):
    id: UUID
    invoice_id: UUID
    number: str
    amount: Decimal
    tax_amount: Decimal
    currency: str
    reason: str
    issued_at: datetime

    model_config = {"from_attributes": True}


class ShareLinkOut(BaseModel):
    token: str
