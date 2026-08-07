from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

SMTP_SECURITY_OPTIONS = {"starttls", "tls", "none"}


class EmailAccountIn(BaseModel):
    label: str
    from_name: str
    from_address: EmailStr
    smtp_host: str
    smtp_port: int
    smtp_security: str = "starttls"
    smtp_username: str
    password: str
    is_default: bool = False

    @field_validator("smtp_security")
    @classmethod
    def validate_security(cls, v: str) -> str:
        if v not in SMTP_SECURITY_OPTIONS:
            raise ValueError(f"smtp_security must be one of {sorted(SMTP_SECURITY_OPTIONS)}")
        return v


class EmailAccountOut(BaseModel):
    id: UUID
    label: str
    from_name: str
    from_address: str
    smtp_host: str
    smtp_port: int
    smtp_security: str
    smtp_username: str
    is_default: bool
    verified_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SendResultOut(BaseModel):
    status: str
    accepted: list[str]
    refused: dict[str, str]
    error_detail: str | None


class InvoiceEmailLogOut(BaseModel):
    id: UUID
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str
    attached_invoice_pdf: bool
    extra_attachments: list[dict]
    status: str
    error_detail: str | None
    sent_at: datetime
    email_account_label: str | None

    model_config = {"from_attributes": True}
