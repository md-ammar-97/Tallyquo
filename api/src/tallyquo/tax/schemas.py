from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PreviewLineIn(BaseModel):
    amount: Decimal
    is_taxable: bool = True


class PreviewTaxIn(BaseModel):
    client_id: UUID
    invoice_date: date
    line_items: list[PreviewLineIn]
    include_provincial_sales_tax: bool = False


class TaxLineOut(BaseModel):
    tax_type: str | None
    label: str
    rate: Decimal | None
    taxable_base: Decimal
    amount: Decimal
    display_note: str | None


class PreviewTaxOut(BaseModel):
    treatment: str
    jurisdiction: str | None
    lines: list[TaxLineOut]
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    warnings: list[str]
    table_version: str
