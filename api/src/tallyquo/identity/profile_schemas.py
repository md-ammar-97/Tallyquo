from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, model_validator


class BusinessProfileIn(BaseModel):
    legal_name: str
    operating_name: str | None = None
    address_line1: str
    address_line2: str | None = None
    city: str
    region_code: str
    postal_code: str
    country_code: str = "CA"
    email: EmailStr | None = None
    phone: str | None = None
    website: str | None = None
    default_currency: str = "CAD"
    default_payment_terms_days: int = 30
    invoice_number_format: str = "{PREFIX}-{YYYY}-{NNN}"
    invoice_number_prefix: str = "INV"
    fiscal_year_start_month: int = 1
    timezone: str = "America/Toronto"


class BusinessProfileOut(BusinessProfileIn):
    tenant_id: UUID
    registration_status: str
    gst_hst_number: str | None
    registration_effective_date: date | None
    logo_ref: str | None
    logo_dark_ref: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RegistrationIn(BaseModel):
    registration_status: str
    gst_hst_number: str | None = None
    registration_effective_date: date | None = None

    @model_validator(mode="after")
    def check_registered_requires_bn(self) -> "RegistrationIn":
        # Mirrors the DB CHECK constraint (registered_requires_bn) so the
        # API returns a field-scoped 422 instead of a raw DB error.
        if self.registration_status == "registered" and (
            self.gst_hst_number is None or self.registration_effective_date is None
        ):
            raise ValueError(
                "gst_hst_number and registration_effective_date are required "
                "when registration_status is 'registered'"
            )
        return self


class PaymentInstructionIn(BaseModel):
    label: str
    method: str
    provider: str | None = None
    account_holder: str | None = None
    currency: str
    fields: dict[str, str] = {}
    is_default: bool = False


class PaymentInstructionOut(BaseModel):
    id: UUID
    label: str
    method: str
    provider: str | None
    account_holder: str | None
    currency: str
    is_default: bool
    fields_masked: dict[str, str]

    model_config = {"from_attributes": True}
