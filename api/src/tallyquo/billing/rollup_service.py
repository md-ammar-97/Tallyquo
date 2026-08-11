"""Client roll-up (period summary) and aging report.

problem-statement.md §6.7, design.md §8.4, datamodel.md §12
(`mv_period_summary`).

Implemented as live aggregate queries rather than the spec's
materialized view: `REFRESH MATERIALIZED VIEW CONCURRENTLY` can't run
inside the RLS-scoped per-request transaction (`tenant_session()` sets
`app.tenant_id` via `SET LOCAL`, which requires an open transaction;
`CONCURRENTLY` forbids one), and a debounced refresh risks showing an
outstanding balance that's already been paid -- the wrong kind of stale
read in a financial product. At the invoice volumes this product
targets (a single sole proprietor), a live `GROUP BY` is cheap; revisit
if that changes.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_AGING_BUCKETS = ("bucket_0_30", "bucket_31_60", "bucket_61_90", "bucket_90_plus")


def _empty_buckets() -> dict[str, Decimal]:
    return {b: Decimal("0") for b in _AGING_BUCKETS}


def _aging_bucket(due_date: date | None, today: date) -> str | None:
    if due_date is None or due_date >= today:
        return None
    days_overdue = (today - due_date).days
    if days_overdue <= 30:
        return "bucket_0_30"
    if days_overdue <= 60:
        return "bucket_31_60"
    if days_overdue <= 90:
        return "bucket_61_90"
    return "bucket_90_plus"


async def client_period_rollup(session: AsyncSession, client_id: UUID) -> list[dict]:
    # design.md §8.4: "month / invoices / billed / collected / outstanding".
    # Mirrors mv_period_summary's aggregation (billed/count exclude
    # cancelled invoices; collected counts a payment recorded before a
    # cancellation), but sums total_cad/payment.amount_cad directly rather
    # than falling back to the native-currency total/amount_paid when a
    # CAD figure is missing (C6) -- a foreign-currency invoice whose FX
    # fetch failed at issue silently omits from these totals instead of
    # being added in as if its USD amount were CAD.
    billed_result = await session.execute(
        text(
            """
            SELECT date_trunc('month', invoice_date)::date AS period,
                   count(*)             AS invoice_count,
                   COALESCE(sum(total_cad), 0) AS billed_cad
            FROM invoice
            WHERE client_id = :client_id AND status NOT IN ('draft', 'cancelled')
            GROUP BY 1
            """
        ),
        {"client_id": client_id},
    )
    billed_by_period = {row.period: (row.invoice_count, row.billed_cad) for row in billed_result.all()}

    collected_result = await session.execute(
        text(
            """
            SELECT date_trunc('month', i.invoice_date)::date AS period,
                   COALESCE(sum(p.amount_cad), 0) AS collected_cad
            FROM invoice i JOIN payment p ON p.invoice_id = i.id
            WHERE i.client_id = :client_id AND i.status <> 'draft'
            GROUP BY 1
            """
        ),
        {"client_id": client_id},
    )
    collected_by_period = {row.period: row.collected_cad for row in collected_result.all()}

    periods = sorted(set(billed_by_period) | set(collected_by_period), reverse=True)
    rows = []
    for period in periods:
        invoice_count, billed = billed_by_period.get(period, (0, Decimal("0")))
        collected = collected_by_period.get(period, Decimal("0"))
        rows.append(
            {
                "period": period,
                "invoice_count": invoice_count,
                "billed_cad": billed,
                "collected_cad": collected,
                "outstanding_cad": billed - collected,
            }
        )
    return rows


async def _outstanding_invoices(session: AsyncSession, *, client_id: UUID | None) -> list[dict]:
    # Raw `status = 'issued'` here isn't a bug -- L15 means partially_paid/
    # overdue/paid are never stored, so every non-cancelled, non-draft,
    # not-fully-paid invoice is still literally 'issued' in the column.
    # Filtering on outstanding balance > 1c does the "not paid" filtering
    # that a stored status column would otherwise be asked to do. That
    # check compares the invoice's own total/amount_paid (same currency as
    # each other, so it's a valid comparison regardless of what currency
    # that is) -- but what gets bucketed for the aggregate report is
    # outstanding_cad specifically (total_cad minus actual CAD received
    # per payment, C6), and invoices without a CAD figure (FX unavailable
    # at issue, edgecases.md C2) are excluded rather than having their
    # foreign total added in as if it were CAD.
    where = "i.status = 'issued' AND (i.total - i.amount_paid) > 0.01 AND i.total_cad IS NOT NULL"
    params: dict = {}
    if client_id is not None:
        where += " AND i.client_id = :client_id"
        params["client_id"] = client_id
    result = await session.execute(
        text(
            f"""
            SELECT i.client_id, c.legal_name AS client_name, i.due_date,
                   i.total_cad - COALESCE(
                     (SELECT sum(p.amount_cad) FROM payment p WHERE p.invoice_id = i.id), 0
                   ) AS outstanding_cad
            FROM invoice i JOIN client c ON c.id = i.client_id
            WHERE {where}
            """
        ),
        params,
    )
    return [dict(r) for r in result.mappings().all()]


async def client_aging(session: AsyncSession, client_id: UUID) -> dict[str, Decimal]:
    today = date.today()
    buckets = _empty_buckets()
    for row in await _outstanding_invoices(session, client_id=client_id):
        bucket = _aging_bucket(row["due_date"], today)
        if bucket:
            buckets[bucket] += row["outstanding_cad"]
    return buckets


async def tenant_aging_report(session: AsyncSession) -> list[dict]:
    today = date.today()
    by_client: dict[UUID, dict] = {}
    for row in await _outstanding_invoices(session, client_id=None):
        bucket = _aging_bucket(row["due_date"], today)
        if bucket is None:
            continue
        entry = by_client.setdefault(
            row["client_id"],
            {"client_id": row["client_id"], "client_name": row["client_name"], **_empty_buckets()},
        )
        entry[bucket] += row["outstanding_cad"]
    rows = list(by_client.values())
    for entry in rows:
        entry["total_outstanding"] = sum((entry[b] for b in _AGING_BUCKETS), start=Decimal("0"))
    rows.sort(key=lambda e: e["total_outstanding"], reverse=True)
    return rows


async def tenant_aging_summary(session: AsyncSession) -> dict:
    """Carbon redesign Dashboard's AR aging chart (dashboard_design.md
    §10): a single tenant-wide summed row, not per-client like
    `tenant_aging_report`. Unlike that report, this also surfaces a
    `not_due` bucket -- `_aging_bucket` returns None (excluded) for
    anything not yet past due, which is right for `tenant_aging_report`
    (an *overdue* list) but would silently drop not-yet-due outstanding
    balances from a chart meant to show the full AR picture."""
    today = date.today()
    buckets = {"not_due": Decimal("0"), **_empty_buckets()}
    for row in await _outstanding_invoices(session, client_id=None):
        bucket = _aging_bucket(row["due_date"], today) or "not_due"
        buckets[bucket] += row["outstanding_cad"]
    buckets["total_outstanding"] = sum(buckets.values(), start=Decimal("0"))
    return buckets


async def tenant_revenue_by_client(session: AsyncSession) -> list[dict]:
    """Carbon redesign Dashboard's Revenue by Client concentration chart
    (dashboard_design.md §13): total billed (not outstanding) per client,
    tenant-wide. Same total_cad-only discipline as `client_period_rollup`
    (C6) -- a foreign-currency invoice whose FX fetch failed at issue is
    excluded rather than folded in as if its native total were CAD."""
    result = await session.execute(
        text(
            """
            SELECT i.client_id, c.legal_name AS client_name,
                   COALESCE(sum(i.total_cad), 0) AS billed_cad
            FROM invoice i JOIN client c ON c.id = i.client_id
            WHERE i.status NOT IN ('draft', 'cancelled') AND i.total_cad IS NOT NULL
            GROUP BY i.client_id, c.legal_name
            ORDER BY billed_cad DESC
            """
        )
    )
    return [dict(r) for r in result.mappings().all()]
