import csv
import io
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import invoices_service as service
from tallyquo.billing import payments_service
from tallyquo.billing import share_service
from tallyquo.billing.invoices_schemas import (
    CreditNoteIn,
    CreditNoteOut,
    InvoiceDocumentOut,
    InvoiceDraftIn,
    InvoiceOut,
    IssueInvoiceIn,
    PaymentIn,
    PaymentOut,
    PreviewDocumentIn,
    ShareLinkOut,
)
from tallyquo.core.auth import CurrentUser, get_current_user, get_db
from tallyquo.notifications import send_service
from tallyquo.notifications.schemas import InvoiceEmailLogOut, SendResultOut

_MAX_TOTAL_ATTACHMENT_BYTES = 20 * 1024 * 1024  # O6: a reasonable cap most SMTP servers share

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


@router.post("/preview-document", response_model=InvoiceDocumentOut)
async def preview_document(
    body: PreviewDocumentIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceDocumentOut:
    try:
        doc = await service.assemble_preview_document(db, current_user.tenant_id, body.model_dump())
    except service.NoBusinessProfile as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except service.ClientNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return InvoiceDocumentOut(**doc)


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


@router.get("/{invoice_id}/document", response_model=InvoiceDocumentOut)
async def get_invoice_document(
    invoice_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceDocumentOut:
    doc = await service.assemble_invoice_document(db, current_user.tenant_id, invoice_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return InvoiceDocumentOut(**doc)


@router.post("/{invoice_id}/cancel", status_code=204)
async def cancel_invoice(
    invoice_id: UUID, reason: str, db: AsyncSession = Depends(get_db)
) -> None:
    found = await service.cancel_invoice(db, invoice_id, reason)
    if not found:
        raise HTTPException(status_code=404, detail="Invoice not found or cannot be cancelled")


@router.get("/{invoice_id}/payments", response_model=list[PaymentOut])
async def list_payments(invoice_id: UUID, db: AsyncSession = Depends(get_db)) -> list[PaymentOut]:
    rows = await payments_service.list_payments(db, invoice_id)
    return [PaymentOut(**row) for row in rows]


@router.post("/{invoice_id}/payments", response_model=PaymentOut, status_code=201)
async def record_payment(
    invoice_id: UUID,
    body: PaymentIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    try:
        row = await payments_service.record_payment(
            db, current_user.tenant_id, invoice_id, current_user.user_id, body.model_dump()
        )
    except payments_service.PaymentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return PaymentOut(**row)


@router.delete("/payments/{payment_id}", status_code=204)
async def reverse_payment(
    payment_id: UUID,
    reason: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    found = await payments_service.reverse_payment(
        db, current_user.tenant_id, payment_id, current_user.user_id, reason
    )
    if not found:
        raise HTTPException(status_code=404, detail="Payment not found")


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


@router.post("/{invoice_id}/share", response_model=ShareLinkOut)
async def create_share_link(
    invoice_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareLinkOut:
    try:
        token = await share_service.get_or_create_share_link(db, current_user.tenant_id, invoice_id)
    except share_service.InvoiceNotShareable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if token is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return ShareLinkOut(token=token)


@router.delete("/{invoice_id}/share", status_code=204)
async def revoke_share_link(invoice_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    found = await share_service.revoke_share_link(db, invoice_id)
    if not found:
        raise HTTPException(status_code=404, detail="No active share link for this invoice")


@router.get("/{invoice_id}/email-log", response_model=list[InvoiceEmailLogOut])
async def list_email_log(invoice_id: UUID, db: AsyncSession = Depends(get_db)) -> list[InvoiceEmailLogOut]:
    rows = await send_service.list_email_log(db, invoice_id)
    return [InvoiceEmailLogOut(**row) for row in rows]


@router.post("/{invoice_id}/email", response_model=SendResultOut)
async def send_invoice_email(
    invoice_id: UUID,
    to_addresses: str = Form(...),
    cc_addresses: str = Form(""),
    subject: str = Form(...),
    body: str = Form(...),
    attach_invoice_pdf: bool = Form(True),
    email_account_id: UUID | None = Form(None),
    extra_files: list[UploadFile] = File(default=[]),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SendResultOut:
    to_list = [a.strip() for a in to_addresses.split(",") if a.strip()]
    cc_list = [a.strip() for a in cc_addresses.split(",") if a.strip()]
    if not to_list:
        raise HTTPException(status_code=422, detail="At least one recipient is required.")

    extra_attachments = []
    total_bytes = 0
    for f in extra_files:
        content = await f.read()
        total_bytes += len(content)
        if total_bytes > _MAX_TOTAL_ATTACHMENT_BYTES:
            # O6: rejected at attach time, before a send is even attempted.
            raise HTTPException(status_code=422, detail="Attachments exceed the 20MB combined size limit.")
        extra_attachments.append(
            send_service.ExtraAttachment(
                filename=f.filename or "attachment",
                content=content,
                mime_type=f.content_type or "application/octet-stream",
            )
        )

    try:
        outcome = await send_service.send_invoice_email(
            db,
            current_user.tenant_id,
            current_user.user_id,
            invoice_id,
            email_account_id=email_account_id,
            to_addresses=to_list,
            cc_addresses=cc_list,
            subject=subject,
            body=body,
            attach_invoice_pdf=attach_invoice_pdf,
            extra_attachments=extra_attachments,
        )
    except send_service.InvoiceNotShareable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except send_service.NoEmailAccount as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    # O10: the send attempt is already logged inside send_invoice_email,
    # in the same transaction as this request. Raising an HTTPException
    # here -- even for a "failed" outcome -- would propagate out through
    # tenant_session()'s `async with session.begin()` and roll that log
    # entry back along with it. A failed send is reported as a normal
    # 200 with status="failed" instead, exactly like a partial refusal.
    return SendResultOut(
        status=outcome.status, accepted=outcome.accepted, refused=outcome.refused, error_detail=outcome.error_detail
    )
