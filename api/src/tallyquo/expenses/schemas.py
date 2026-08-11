from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ExpenseCategoryOut(BaseModel):
    id: UUID
    name: str
    t2125_line: str | None
    deductible_pct: Decimal
    is_capital: bool

    model_config = {"from_attributes": True}


class ExpenseIn(BaseModel):
    expense_date: date
    vendor: str | None = None
    description: str | None = None
    category_id: UUID | None = None
    currency: str = "CAD"
    amount_total: Decimal
    tax_amount: Decimal = Decimal("0")
    tax_type: str | None = None
    business_use_pct: Decimal = Decimal("100.00")
    client_id: UUID | None = None
    payment_method: str | None = None
    receipt_id: UUID | None = None


class ExpenseOut(BaseModel):
    id: UUID
    expense_date: date
    vendor: str | None
    description: str | None
    category_id: UUID | None
    category_name: str | None
    t2125_line: str | None
    deductible_pct: Decimal | None
    is_capital: bool | None
    currency: str
    amount_total: Decimal
    tax_amount: Decimal
    tax_type: str | None
    amount_net: Decimal
    business_use_pct: Decimal
    itc_eligible: bool
    client_id: UUID | None
    is_rebilled: bool
    rebilled_invoice_id: UUID | None
    payment_method: str | None
    source: str
    ocr_confidence: Decimal | None
    created_at: datetime
    warning: str | None = None

    model_config = {"from_attributes": True}


class ReceiptOcrOut(BaseModel):
    vendor: str | None
    date: str | None
    amount: str | None
    confidence: float | None


class ReceiptUploadOut(BaseModel):
    id: UUID
    expense_id: UUID | None
    file_ref: str
    already_existed: bool
    ocr: ReceiptOcrOut | None


class UnprocessedReceiptOut(BaseModel):
    id: UUID
    file_ref: str
    mime_type: str
    byte_size: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ExpenseByCategoryOut(BaseModel):
    category_id: UUID | None
    category_name: str
    amount: Decimal


class ReceiptCompletenessOut(BaseModel):
    total: int
    with_receipt: int
    missing: int
    pct: float | None
