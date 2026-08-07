"""Compose-and-send an issued invoice by email. edgecases.md §8.

O1: this is only ever reached by an explicit user action with an
explicit send confirmation -- nothing here is called from a scheduled
job. O10: every attempt is logged to invoice_email_log regardless of
outcome, the durable "was this invoice emailed, to whom" record kept
distinct from the invoice's own frozen snapshot.

Extra attachments are taken as raw bytes and logged by filename/size
only (not persisted to object storage) -- deliberately: this feature
must work even before Supabase Storage S3 keys exist (`implementation_
plan.md` 2.8's known gap), and there's no legitimate need to re-download
a one-time email attachment later the way there is for a receipt.
"""

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import invoices_service
from tallyquo.notifications import email_accounts_service, smtp_client


class InvoiceNotShareable(Exception):
    """Draft invoices have nothing final to send yet."""


class NoEmailAccount(Exception):
    """No SMTP account configured, or the one requested doesn't exist."""


@dataclass
class ExtraAttachment:
    filename: str
    content: bytes
    mime_type: str


@dataclass
class SendOutcome:
    status: str  # sent | failed
    accepted: list[str]
    refused: dict[str, str]
    error_detail: str | None


async def send_invoice_email(
    session: AsyncSession,
    tenant_id: UUID,
    actor_id: UUID,
    invoice_id: UUID,
    *,
    email_account_id: UUID | None,
    to_addresses: list[str],
    cc_addresses: list[str],
    subject: str,
    body: str,
    attach_invoice_pdf: bool,
    extra_attachments: list[ExtraAttachment],
) -> SendOutcome:
    invoice = await invoices_service.get_invoice(session, invoice_id)
    if invoice is None:
        raise InvoiceNotShareable("Invoice not found.")
    if invoice["status"] == "draft":
        raise InvoiceNotShareable("Issue this invoice before emailing it.")

    if email_account_id is None:
        email_account_id = await email_accounts_service.get_default_account_id(session)
    if email_account_id is None:
        raise NoEmailAccount("Add an email account before sending.")
    config = await email_accounts_service.load_smtp_config(session, email_account_id)
    if config is None:
        raise NoEmailAccount("That email account no longer exists.")

    attachments = []
    if attach_invoice_pdf:
        pdf_bytes = await invoices_service.render_pdf(session, tenant_id, invoice_id)
        if pdf_bytes is not None:
            filename = f"{invoice['number'] or 'invoice'}.pdf"
            attachments.append(smtp_client.Attachment(filename=filename, content=pdf_bytes, mime_type="application/pdf"))
    for extra in extra_attachments:
        attachments.append(smtp_client.Attachment(filename=extra.filename, content=extra.content, mime_type=extra.mime_type))

    log_id = uuid4()
    extra_meta = [{"filename": a.filename, "byte_size": len(a.content)} for a in extra_attachments]

    try:
        result = await smtp_client.send(
            config,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            subject=subject,
            body=body,
            attachments=attachments,
        )
        outcome = SendOutcome(
            status="sent",
            accepted=result.accepted,
            refused=result.refused,
            error_detail=None if result.fully_sent else f"Refused: {json.dumps(result.refused)}",
        )
    except smtp_client.SmtpSendFailed as exc:
        outcome = SendOutcome(status="failed", accepted=[], refused={}, error_detail=str(exc))

    # O10: logged regardless of outcome -- append-only, never mutated after.
    await session.execute(
        text(
            "INSERT INTO invoice_email_log "
            "(id, tenant_id, invoice_id, email_account_id, to_addresses, cc_addresses, "
            " subject, body, attached_invoice_pdf, extra_attachments, sent_by_user_id, "
            " status, error_detail) "
            "VALUES (:id, :tenant_id, :invoice_id, :email_account_id, :to_addresses, "
            " :cc_addresses, :subject, :body, :attach_invoice_pdf, :extra_attachments, "
            " :actor_id, :status, :error_detail)"
        ),
        {
            "id": log_id,
            "tenant_id": tenant_id,
            "invoice_id": invoice_id,
            "email_account_id": email_account_id,
            "to_addresses": json.dumps(to_addresses),
            "cc_addresses": json.dumps(cc_addresses),
            "subject": subject,
            "body": body,
            "attach_invoice_pdf": attach_invoice_pdf,
            "extra_attachments": json.dumps(extra_meta),
            "actor_id": actor_id,
            "status": outcome.status,
            "error_detail": outcome.error_detail,
        },
    )
    return outcome


async def list_email_log(session: AsyncSession, invoice_id: UUID) -> list[dict]:
    result = await session.execute(
        text(
            "SELECT l.id, l.to_addresses, l.cc_addresses, l.subject, "
            "l.attached_invoice_pdf, l.extra_attachments, l.status, l.error_detail, l.sent_at, "
            "a.label AS email_account_label "
            "FROM invoice_email_log l LEFT JOIN email_account a ON a.id = l.email_account_id "
            "WHERE l.invoice_id = :id ORDER BY l.sent_at DESC"
        ),
        {"id": invoice_id},
    )
    return [dict(r) for r in result.mappings().all()]
