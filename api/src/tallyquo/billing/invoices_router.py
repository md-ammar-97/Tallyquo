from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import invoices_service as service
from tallyquo.billing.invoices_schemas import (
    CreditNoteIn,
    CreditNoteOut,
    InvoiceDraftIn,
    InvoiceOut,
    IssueInvoiceIn,
)
from tallyquo.core.auth import CurrentUser, get_current_user, get_db

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceOut])
async def list_invoices(db: AsyncSession = Depends(get_db)) -> list[InvoiceOut]:
    rows = await service.list_invoices(db)
    return [InvoiceOut(**row) for row in rows]


@router.post("", response_model=InvoiceOut, status_code=201)
async def create_draft(
    body: InvoiceDraftIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    data = body.model_dump()
    data["line_items"] = [li for li in data["line_items"]]
    row = await service.create_draft(db, current_user.tenant_id, data)
    return InvoiceOut(**row)


@router.get("/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(invoice_id: UUID, db: AsyncSession = Depends(get_db)) -> InvoiceOut:
    row = await service.get_invoice(db, invoice_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return InvoiceOut(**row)


@router.patch("/{invoice_id}", response_model=InvoiceOut)
async def update_draft(
    invoice_id: UUID,
    body: InvoiceDraftIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    try:
        row = await service.update_draft(db, current_user.tenant_id, invoice_id, body.model_dump())
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found") from None
    except service.InvoiceNotDraft as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return InvoiceOut(**row)


@router.post("/{invoice_id}/issue", response_model=InvoiceOut)
async def issue_invoice(
    invoice_id: UUID,
    body: IssueInvoiceIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    try:
        row = await service.issue_invoice(
            db, current_user.tenant_id, current_user.user_id, invoice_id, body.confirm_zero_total
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found") from None
    except service.InvoiceNotDraft as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except service.ComplianceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return InvoiceOut(**row)


@router.post("/{invoice_id}/cancel", status_code=204)
async def cancel_invoice(
    invoice_id: UUID, reason: str, db: AsyncSession = Depends(get_db)
) -> None:
    found = await service.cancel_invoice(db, invoice_id, reason)
    if not found:
        raise HTTPException(status_code=404, detail="Invoice not found or cannot be cancelled")


@router.post("/{invoice_id}/credit-note", response_model=CreditNoteOut, status_code=201)
async def create_credit_note(
    invoice_id: UUID,
    body: CreditNoteIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreditNoteOut:
    row = await service.create_credit_note(db, current_user.tenant_id, invoice_id, body.model_dump())
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found or not yet issued")
    return CreditNoteOut(**row)
