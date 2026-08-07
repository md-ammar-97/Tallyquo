from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class RequestOtpIn(BaseModel):
    email: EmailStr


class RequestOtpOut(BaseModel):
    # Identical for every input -- known email, unknown email, or
    # rate-limited -- so the response itself can never be used to enumerate
    # accounts or reveal which rate limit was hit (edgecases.md A1, A2).
    message: str = "If that email is valid, a code has been sent."


class VerifyOtpIn(BaseModel):
    email: EmailStr
    code: str
    device_label: str | None = None


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class SessionOut(BaseModel):
    id: UUID
    device_label: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    is_current: bool

    model_config = {"from_attributes": True}
