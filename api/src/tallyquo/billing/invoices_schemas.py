from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


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
    line_items: list[InvoiceLineOut] = []
    tax_lines: list[InvoiceTaxLineOut] = []

    model_config = {"from_attributes": True}


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
