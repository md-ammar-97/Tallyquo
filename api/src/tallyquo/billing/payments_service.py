"""Payment recording. edgecases.md §7 (L10-L12) -- payments never mutate
the invoice's frozen tax snapshot, only amount_paid, which
invoices_service.py's effective-status expression reads back."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

OVERPAYMENT_TOLERANCE = Decimal("0.01")


class PaymentError(Exception):
    """User-facing: invoice not found, cancelled, or payment would overpay."""


async def record_payment(
    session: AsyncSession, tenant_id: UUID, invoice_id: UUID, actor_id: UUID, data: dict
) -> dict:
    invoice_row = (
        await session.execute(
            text("SELECT status, total, amount_paid, currency FROM invoice WHERE id = :id"),
            {"id": invoice_id},
        )
    ).mappings().first()
    if invoice_row is None:
        raise PaymentError("Invoice not found.")
    if invoice_row["status"] == "cancelled":
        # L11: payment blocked on a cancelled invoice.
        raise PaymentError("This invoice is cancelled -- payments can't be recorded against it.")
    if invoice_row["status"] == "draft":
        raise PaymentError("This invoice hasn't been issued yet.")

    new_total_paid = invoice_row["amount_paid"] + data["amount"]
    if new_total_paid > invoice_row["total"] + OVERPAYMENT_TOLERANCE:
        # L10: blocked above a 1-cent tolerance; an overpayment credit is
        # the spec'd alternative (not yet built -- Phase 2 doesn't include
        # a credit-balance concept, so this is surfaced as a clear error
        # rather than a half-built workaround).
        raise PaymentError(
            f"That would overpay this invoice by "
            f"{new_total_paid - invoice_row['total']:.2f} {invoice_row['currency']}. "
            "Record a smaller amount, or issue a credit note first."
        )

    payment_id = uuid4()
    amount_cad = data["amount"] if invoice_row["currency"] == "CAD" else None
    await session.execute(
        text(
            "INSERT INTO payment (id, tenant_id, invoice_id, amount, currency, amount_cad, "
            "received_date, method, reference, note) "
            "VALUES (:id, :tenant_id, :invoice_id, :amount, :currency, :amount_cad, "
            ":received_date, :method, :reference, :note)"
        ),
        {
            "id": payment_id,
            "tenant_id": tenant_id,
            "invoice_id": invoice_id,
            "currency": invoice_row["currency"],
            "amount_cad": amount_cad,
            **data,
        },
    )
    await session.execute(
        text("UPDATE invoice SET amount_paid = :paid WHERE id = :id"),
        {"paid": new_total_paid, "id": invoice_id},
    )
    await session.execute(
        text(
            "INSERT INTO audit_log (tenant_id, actor_user_id, actor_kind, action, "
            "entity_type, entity_id, after) "
            "VALUES (:tenant_id, :actor_id, 'user', 'payment.recorded', 'payment', :entity_id, :after)"
        ),
        {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "entity_id": payment_id,
            "after": f'{{"amount": "{data["amount"]}", "invoice_id": "{invoice_id}"}}',
        },
    )

    row = (
        await session.execute(
            text(
                "SELECT id, invoice_id, amount, currency, received_date, method, reference, note, created_at "
                "FROM payment WHERE id = :id"
            ),
            {"id": payment_id},
        )
    ).mappings().one()
    return dict(row)


async def list_payments(session: AsyncSession, invoice_id: UUID) -> list[dict]:
    result = await session.execute(
        text(
            "SELECT id, invoice_id, amount, currency, received_date, method, reference, note, created_at "
            "FROM payment WHERE invoice_id = :id ORDER BY received_date DESC, created_at DESC"
        ),
        {"id": invoice_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def reverse_payment(session: AsyncSession, tenant_id: UUID, payment_id: UUID, actor_id: UUID, reason: str) -> bool:
    # L12: "Delete the payment record with a reason; status recalculates.
    # Audited." -- an explicit hard delete, not a soft-delete flag, but the
    # audit_log entry (append-only, UPDATE/DELETE revoked from the app
    # role) preserves the before-state permanently.
    row = (
        await session.execute(
            text("SELECT invoice_id, amount FROM payment WHERE id = :id"), {"id": payment_id}
        )
    ).mappings().first()
    if row is None:
        return False

    await session.execute(
        text(
            "INSERT INTO audit_log (tenant_id, actor_user_id, actor_kind, action, "
            "entity_type, entity_id, before, after) "
            "VALUES (:tenant_id, :actor_id, 'user', 'payment.reversed', 'payment', :entity_id, :before, :after)"
        ),
        {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "entity_id": payment_id,
            "before": f'{{"amount": "{row["amount"]}", "invoice_id": "{row["invoice_id"]}"}}',
            "after": f'{{"reason": "{reason}"}}',
        },
    )
    await session.execute(text("DELETE FROM payment WHERE id = :id"), {"id": payment_id})
    await session.execute(
        text("UPDATE invoice SET amount_paid = amount_paid - :amount WHERE id = :id"),
        {"amount": row["amount"], "id": row["invoice_id"]},
    )
    return True
