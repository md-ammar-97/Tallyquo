import csv
import io
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
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
async def list_invoices(
    db: AsyncSession = Depends(get_db),
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: UUID | None = None,
    status: str | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    currency: str | None = None,
    tax_treatment: str | None = None,
) -> list[InvoiceOut]:
    rows = await service.list_invoices(
        db,
        date_from=date_from,
        date_to=date_to,
        client_id=client_id,
        status=status,
        min_amount=min_amount,
        max_amount=max_amount,
        currency=currency,
        tax_treatment=tax_treatment,
    )
    return [InvoiceOut(**row) for row in rows]


@router.get("/export.csv")
async def export_invoices_csv(
    db: AsyncSession = Depends(get_db),
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: UUID | None = None,
    status: str | None = None,
    currency: str | None = None,
) -> Response:
    rows = await service.list_invoices(
        db, date_from=date_from, date_to=date_to, client_id=client_id, status=status, currency=currency
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["number", "status", "invoice_date", "due_date", "currency", "subtotal", "tax_total", "total", "tax_treatment"]
    )
    for row in rows:
        writer.writerow(
            [
                row["number"] or "",
                row["status"],
                row["invoice_date"] or "",
                row["due_date"] or "",
                row["currency"],
                row["subtotal"],
                row["tax_total"],
                row["total"],
                row["tax_treatment_snapshot"] or "",
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )


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


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    pdf_bytes = await service.render_pdf(db, current_user.tenant_id, invoice_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return Response(content=pdf_bytes, media_type="application/pdf")


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
