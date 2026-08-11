from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, model_validator

TAX_TREATMENTS = {"not_registered", "taxable", "zero_rated_export", "exempt"}


class ClientIn(BaseModel):
    legal_name: str
    display_name: str | None = None
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None

    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region_code: str | None = None
    postal_code: str | None = None
    country_code: str

    tax_treatment: str
    is_gst_registered: bool | None = None
    treatment_override_reason: str | None = None

    default_currency: str = "CAD"
    default_payment_terms_days: int | None = None
    default_rate: Decimal | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_treatment(self) -> "ClientIn":
        if self.tax_treatment not in TAX_TREATMENTS:
            raise ValueError(f"tax_treatment must be one of {sorted(TAX_TREATMENTS)}")
        if self.tax_treatment == "taxable" and not self.region_code:
            # datamodel.md taxable_requires_region -- surfaced here as a
            # clean 422 instead of a DB constraint error.
            raise ValueError(
                "region_code is required when tax_treatment is 'taxable' "
                "(edgecases.md D7: the rate depends on where your client is)"
            )
        return self


class ClientOut(ClientIn):
    id: UUID
    created_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class ClientEvidenceIn(BaseModel):
    # Metadata only -- actual file upload wires through core/storage.py once
    # S3 access keys exist for the Supabase project (none needed yet: no
    # upload endpoint has been built before this one). file_hash is
    # provided by the caller for now; once storage.py is wired in, the API
    # will compute it server-side from the uploaded bytes instead.
    kind: str
    file_ref: str
    file_hash: str
    effective_date: str | None = None
    expires_at: str | None = None
    note: str | None = None


class ClientEvidenceOut(BaseModel):
    id: UUID
    kind: str
    file_ref: str
    effective_date: str | None
    expires_at: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ClientPeriodOut(BaseModel):
    period: date
    invoice_count: int
    billed_cad: Decimal
    collected_cad: Decimal
    outstanding_cad: Decimal

    model_config = {"from_attributes": True}


class AgingBucketsOut(BaseModel):
    bucket_0_30: Decimal
    bucket_31_60: Decimal
    bucket_61_90: Decimal
    bucket_90_plus: Decimal


class ClientRollupOut(BaseModel):
    periods: list[ClientPeriodOut]
    aging: AgingBucketsOut


class AgingReportRowOut(AgingBucketsOut):
    client_id: UUID
    client_name: str
    total_outstanding: Decimal


class ClientSummaryOut(ClientOut):
    outstanding_cad: Decimal
    has_overdue: bool


class ClientSummaryPageOut(BaseModel):
    items: list[ClientSummaryOut]
    total: int


class AgingSummaryOut(AgingBucketsOut):
    not_due: Decimal
    total_outstanding: Decimal


class RevenueByClientRowOut(BaseModel):
    client_id: UUID
    client_name: str
    billed_cad: Decimal


class PaymentSpeedOut(BaseModel):
    invoice_count: int
    average_days: float | None
