from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from tallyquo.core.auth import CurrentUser, get_current_user
from tallyquo.identity import service
from tallyquo.identity.schemas import (
    RefreshIn,
    RequestOtpIn,
    RequestOtpOut,
    SessionOut,
    TokenPairOut,
    VerifyOtpIn,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/request-otp", response_model=RequestOtpOut)
async def request_otp(body: RequestOtpIn, request: Request) -> RequestOtpOut:
    await service.request_otp(body.email, _client_ip(request))
    return RequestOtpOut()


@router.post("/verify-otp", response_model=TokenPairOut)
async def verify_otp(body: VerifyOtpIn, request: Request) -> TokenPairOut:
    try:
        tokens = await service.verify_otp(body.email, body.code, body.device_label, _client_ip(request))
    except (service.OtpInvalid, service.OtpExpired) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from None
    return TokenPairOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh", response_model=TokenPairOut)
async def refresh(body: RefreshIn, request: Request) -> TokenPairOut:
    try:
        tokens = await service.refresh_session(body.refresh_token, _client_ip(request))
    except service.RefreshTokenInvalid as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from None
    return TokenPairOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/logout", status_code=204)
async def logout(current_user: CurrentUser = Depends(get_current_user)) -> None:
    await service.logout(current_user.tenant_id, current_user.session_id)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(current_user: CurrentUser = Depends(get_current_user)) -> list[SessionOut]:
    rows = await service.list_sessions(current_user.tenant_id, current_user.user_id)
    return [
        SessionOut(**row, is_current=row["id"] == current_user.session_id) for row in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: UUID, current_user: CurrentUser = Depends(get_current_user)
) -> None:
    found = await service.revoke_session(current_user.tenant_id, current_user.user_id, session_id)
    if not found:
        raise HTTPException(status_code=404, detail="Session not found")
