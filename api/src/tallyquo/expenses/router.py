from datetime import date
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.auth import CurrentUser, get_current_user, get_db
from tallyquo.core.storage import UnrecognizedFileType
from tallyquo.expenses import receipts_service
from tallyquo.expenses import service
from tallyquo.expenses.schemas import (
    ExpenseCategoryOut,
    ExpenseIn,
    ExpenseOut,
    ReceiptUploadOut,
    UnprocessedReceiptOut,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("/categories", response_model=list[ExpenseCategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)) -> list[ExpenseCategoryOut]:
    rows = await service.list_categories(db)
    return [ExpenseCategoryOut(**row) for row in rows]


@router.get("", response_model=list[ExpenseOut])
async def list_expenses(
    db: AsyncSession = Depends(get_db),
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: UUID | None = None,
    client_id: UUID | None = None,
) -> list[ExpenseOut]:
    rows = await service.list_expenses(
        db, date_from=date_from, date_to=date_to, category_id=category_id, client_id=client_id
    )
    return [ExpenseOut(**row) for row in rows]


@router.post("", response_model=ExpenseOut, status_code=201)
async def create_expense(
    body: ExpenseIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExpenseOut:
    data = body.model_dump()
    receipt_id = data.pop("receipt_id", None)
    row = await service.create_expense(db, current_user.tenant_id, current_user.user_id, data, receipt_id=receipt_id)
    return ExpenseOut(**row, warning=service.closed_year_warning(row["expense_date"]))


@router.get("/receipts/unprocessed", response_model=list[UnprocessedReceiptOut])
async def unprocessed_receipts(db: AsyncSession = Depends(get_db)) -> list[UnprocessedReceiptOut]:
    rows = await receipts_service.unprocessed_receipts(db)
    return [UnprocessedReceiptOut(**row) for row in rows]


@router.post("/receipts", response_model=ReceiptUploadOut, status_code=201)
async def upload_receipt(
    file: UploadFile,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptUploadOut:
    data = await file.read()
    try:
        row = await receipts_service.upload_receipt(db, current_user.tenant_id, data)
    except UnrecognizedFileType as exc:
        # E13: rejected at upload, accepted formats named, validated by
        # content not extension.
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except (RuntimeError, ClientError, BotoCoreError):
        # Storage not configured, or the configured credentials/endpoint
        # rejected the request -- a deploy-config gap, not a user error.
        # Never surfaced as a raw 500: an unhandled exception here would
        # skip Starlette's CORSMiddleware entirely (it wraps normal
        # responses, not ones from the outer ServerErrorMiddleware), which
        # the browser reports as a misleading "CORS blocked" error instead
        # of the real cause. Manual entry (no receipt) still works either way.
        raise HTTPException(
            status_code=503, detail="Receipt storage isn't available right now. You can still enter this expense manually."
        ) from None
    return ReceiptUploadOut(**row)


@router.get("/receipts/{receipt_id}/url")
async def get_receipt_url(receipt_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    url = await receipts_service.signed_receipt_url(db, receipt_id)
    if url is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"url": url}


@router.get("/{expense_id}", response_model=ExpenseOut)
async def get_expense(expense_id: UUID, db: AsyncSession = Depends(get_db)) -> ExpenseOut:
    row = await service.get_expense(db, expense_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return ExpenseOut(**row, warning=service.closed_year_warning(row["expense_date"]))


@router.patch("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: UUID,
    body: ExpenseIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExpenseOut:
    data = body.model_dump()
    data.pop("receipt_id", None)
    row = await service.update_expense(db, current_user.tenant_id, expense_id, data)
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return ExpenseOut(**row, warning=service.closed_year_warning(row["expense_date"]))


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(expense_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    found = await service.delete_expense(db, expense_id)
    if not found:
        raise HTTPException(status_code=404, detail="Expense not found")


@router.post("/{expense_id}/rebill", response_model=ExpenseOut)
async def rebill_expense(expense_id: UUID, invoice_id: UUID, db: AsyncSession = Depends(get_db)) -> ExpenseOut:
    row = await service.mark_rebilled(db, expense_id, invoice_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return ExpenseOut(**row, warning=service.closed_year_warning(row["expense_date"]))
