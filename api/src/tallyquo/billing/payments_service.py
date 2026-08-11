"""Payment recording. edgecases.md §7 (L10-L12) -- payments never mutate
the invoice's frozen tax snapshot, only amount_paid, which
invoices_service.py's effective-status expression reads back.

C3/C4: each payment captures its own FX rate at its own received_date --
never the invoice's issue-time rate -- and fx_gain_loss is computed once
here and stored, isolating the FX movement as its own explicit figure
rather than letting it get silently absorbed into revenue.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import fx

OVERPAYMENT_TOLERANCE = Decimal("0.01")

_PAYMENT_COLUMNS = (
    "id, invoice_id, amount, currency, amount_cad, fx_rate_to_cad, fx_gain_loss, "
    "received_date, method, reference, note, created_at"
)


class PaymentError(Exception):
    """User-facing: invoice not found, cancelled, or payment would overpay."""


async def record_payment(
    session: AsyncSession, tenant_id: UUID, invoice_id: UUID, actor_id: UUID, data: dict
) -> dict:
    invoice_row = (
        await session.execute(
            text(
                "SELECT status, total, amount_paid, currency, fx_rate_to_cad "
                "FROM invoice WHERE id = :id"
            ),
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
    amount_cad: Decimal | None
    fx_rate_to_cad: Decimal | None
    fx_gain_loss: Decimal | None
    if invoice_row["currency"] == "CAD":
        amount_cad, fx_rate_to_cad, fx_gain_loss = data["amount"], None, None
    else:
        # C2's "never block" applies here too, for consistency: a payment
        # still records if the FX source is down when it's entered, just
        # without a CAD figure or gain/loss until it's revisited.
        fx_result = await fx.fetch_rate(invoice_row["currency"], data["received_date"])
        if fx_result is None:
            amount_cad, fx_rate_to_cad, fx_gain_loss = None, None, None
        else:
            fx_rate_to_cad = fx_result.rate
            amount_cad = fx.convert(data["amount"], fx_result.rate)
            fx_gain_loss = None
            if invoice_row["fx_rate_to_cad"] is not None:
                # C3: this payment's actual CAD value vs. what it would
                # have been worth at the invoice's frozen issue-time rate.
                at_invoice_rate = fx.convert(data["amount"], invoice_row["fx_rate_to_cad"])
                fx_gain_loss = amount_cad - at_invoice_rate

    await session.execute(
        text(
            "INSERT INTO payment (id, tenant_id, invoice_id, amount, currency, amount_cad, "
            "fx_rate_to_cad, fx_gain_loss, received_date, method, reference, note) "
            "VALUES (:id, :tenant_id, :invoice_id, :amount, :currency, :amount_cad, "
            ":fx_rate_to_cad, :fx_gain_loss, :received_date, :method, :reference, :note)"
        ),
        {
            "id": payment_id,
            "tenant_id": tenant_id,
            "invoice_id": invoice_id,
            "currency": invoice_row["currency"],
            "amount_cad": amount_cad,
            "fx_rate_to_cad": fx_rate_to_cad,
            "fx_gain_loss": fx_gain_loss,
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
            text(f"SELECT {_PAYMENT_COLUMNS} FROM payment WHERE id = :id"),
            {"id": payment_id},
        )
    ).mappings().one()
    return dict(row)


async def list_payments(session: AsyncSession, invoice_id: UUID) -> list[dict]:
    result = await session.execute(
        text(
            f"SELECT {_PAYMENT_COLUMNS} FROM payment "
            "WHERE invoice_id = :id ORDER BY received_date DESC, created_at DESC"
        ),
        {"id": invoice_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def average_days_to_payment(session: AsyncSession) -> dict:
    """Carbon redesign Dashboard's Payment Collection Performance section
    (dashboard_design.md §12) -- v1 scope, deliberately: for each fully
    paid invoice, the gap between invoice_date and the LATEST payment
    recorded against it, averaged tenant-wide. This assumes payments are
    entered in roughly chronological order (a backdated, out-of-sequence
    entry could skew an individual invoice's figure slightly) -- an
    honest, stated simplification, not a silent one. The trend sparkline
    and fastest/slowest-paying-client breakdown from the same spec
    section are deliberately NOT built here: both need real additional
    complexity (historical-period computation, and a minimum-sample-size
    guard respectively, since a client with exactly one invoice would
    otherwise look definitively "fastest" or "slowest" off one data
    point) -- scoped-out follow-up work, not an oversight.

    "Paid" is checked directly (amount_paid >= total AND total > 0)
    rather than via invoices_service.py's full _EFFECTIVE_STATUS_EXPR --
    equivalent for this branch (paid is evaluated before the overdue
    check, which is the only branch needing the business_profile
    timezone join), without pulling in that join for a query that
    doesn't otherwise need it.
    """
    result = await session.execute(
        text(
            """
            WITH paid_invoices AS (
              SELECT i.id, i.invoice_date, max(p.received_date) AS last_payment_date
              FROM invoice i JOIN payment p ON p.invoice_id = i.id
              WHERE i.status NOT IN ('cancelled', 'draft')
                AND i.amount_paid >= i.total AND i.total > 0
              GROUP BY i.id, i.invoice_date
            )
            SELECT count(*) AS invoice_count,
                   avg(last_payment_date - invoice_date) AS average_days
            FROM paid_invoices
            """
        )
    )
    row = result.mappings().one()
    average_days = row["average_days"]
    return {
        "invoice_count": row["invoice_count"],
        "average_days": round(float(average_days), 1) if average_days is not None else None,
    }


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
