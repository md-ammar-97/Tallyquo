from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.auth import CurrentUser, get_current_user, get_db
from tallyquo.identity import profile_service as service
from tallyquo.identity.profile_schemas import (
    BusinessProfileIn,
    BusinessProfileOut,
    PaymentInstructionIn,
    PaymentInstructionOut,
    RegistrationIn,
)

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=BusinessProfileOut | None)
async def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessProfileOut | None:
    profile = await service.get_profile(db, current_user.tenant_id)
    return BusinessProfileOut(**profile) if profile else None


@router.patch("/profile", response_model=BusinessProfileOut)
async def update_profile(
    body: BusinessProfileIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessProfileOut:
    profile = await service.upsert_profile(db, current_user.tenant_id, body.model_dump())
    return BusinessProfileOut(**profile)


@router.patch("/profile/registration", response_model=BusinessProfileOut)
async def update_registration(
    body: RegistrationIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessProfileOut:
    try:
        profile = await service.update_registration(db, current_user.tenant_id, body.model_dump())
    except Exception as exc:  # noqa: BLE001 -- surface a clean 422 for the NOT NULL case
        raise HTTPException(
            status_code=422,
            detail="Add the rest of your business profile before setting registration status.",
        ) from exc
    return BusinessProfileOut(**profile)


@router.post("/profile/logo", response_model=BusinessProfileOut)
async def upload_logo(
    file: UploadFile,
    variant: str = "light",
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessProfileOut:
    data = await file.read()
    try:
        profile = await service.upload_logo(db, current_user.tenant_id, data, variant)
    except service.InvalidLogoFile as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return BusinessProfileOut(**profile)


@router.get("/payment-instructions", response_model=list[PaymentInstructionOut])
async def list_payment_instructions(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentInstructionOut]:
    rows = await service.list_payment_instructions(db, current_user.tenant_id)
    return [PaymentInstructionOut(**row) for row in rows]


@router.post("/payment-instructions", response_model=PaymentInstructionOut, status_code=201)
async def create_payment_instruction(
    body: PaymentInstructionIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentInstructionOut:
    row = await service.create_payment_instruction(db, current_user.tenant_id, body.model_dump())
    return PaymentInstructionOut(**row)


@router.get("/payment-instructions/{instruction_id}/reveal")
async def reveal_payment_instruction(
    instruction_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await service.reveal_payment_instruction(db, current_user.tenant_id, instruction_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Payment instruction not found")
    return row


@router.delete("/payment-instructions/{instruction_id}", status_code=204)
async def archive_payment_instruction(
    instruction_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    found = await service.archive_payment_instruction(db, current_user.tenant_id, instruction_id)
    if not found:
        raise HTTPException(status_code=404, detail="Payment instruction not found")
