from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.auth import CurrentUser, get_current_user, get_db
from tallyquo.notifications import email_accounts_service as service
from tallyquo.notifications import smtp_client
from tallyquo.notifications.schemas import EmailAccountIn, EmailAccountOut

router = APIRouter(prefix="/email-accounts", tags=["notifications"])


@router.get("", response_model=list[EmailAccountOut])
async def list_accounts(db: AsyncSession = Depends(get_db)) -> list[EmailAccountOut]:
    rows = await service.list_accounts(db)
    return [EmailAccountOut(**row) for row in rows]


@router.post("", response_model=EmailAccountOut, status_code=201)
async def create_account(
    body: EmailAccountIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmailAccountOut:
    row = await service.create_account(db, current_user.tenant_id, body.model_dump())
    return EmailAccountOut(**row)


@router.post("/{account_id}/verify", status_code=204)
async def verify_account(account_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    try:
        await service.verify_account(db, account_id)
    except service.AccountNotFound:
        raise HTTPException(status_code=404, detail="Email account not found") from None
    except smtp_client.SmtpSendFailed as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.delete("/{account_id}", status_code=204)
async def archive_account(account_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    found = await service.archive_account(db, account_id)
    if not found:
        raise HTTPException(status_code=404, detail="Email account not found")
