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
    # Mirrors mv_period_summary's aggregation exactly (billed/count exclude
    # cancelled invoices; collected sums amount_paid across everything
    # non-draft, since a payment recorded before a cancellation still
    # happened).
    result = await session.execute(
        text(
            """
            SELECT date_trunc('month', invoice_date)::date AS period,
                   count(*) FILTER (WHERE status <> 'cancelled')                                    AS invoice_count,
                   COALESCE(sum(COALESCE(total_cad, total)) FILTER (WHERE status <> 'cancelled'), 0) AS billed_cad,
                   COALESCE(sum(amount_paid), 0)                                                     AS collected_cad
            FROM invoice
            WHERE client_id = :client_id AND status <> 'draft'
            GROUP BY 1
            ORDER BY 1 DESC
            """
        ),
        {"client_id": client_id},
    )
    rows = [dict(r) for r in result.mappings().all()]
    for r in rows:
        r["outstanding_cad"] = r["billed_cad"] - r["collected_cad"]
    return rows


async def _outstanding_invoices(session: AsyncSession, *, client_id: UUID | None) -> list[dict]:
    # Raw `status = 'issued'` here isn't a bug -- L15 means partially_paid/
    # overdue/paid are never stored, so every non-cancelled, non-draft,
    # not-fully-paid invoice is still literally 'issued' in the column.
    # Filtering on outstanding balance > 1c does the "not paid" filtering
    # that a stored status column would otherwise be asked to do.
    where = "i.status = 'issued' AND (i.total - i.amount_paid) > 0.01"
    params: dict = {}
    if client_id is not None:
        where += " AND i.client_id = :client_id"
        params["client_id"] = client_id
    result = await session.execute(
        text(
            f"SELECT i.client_id, c.legal_name AS client_name, i.due_date, i.total, i.amount_paid "
            f"FROM invoice i JOIN client c ON c.id = i.client_id WHERE {where}"
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
            buckets[bucket] += row["total"] - row["amount_paid"]
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
        entry[bucket] += row["total"] - row["amount_paid"]
    rows = list(by_client.values())
    for entry in rows:
        entry["total_outstanding"] = sum((entry[b] for b in _AGING_BUCKETS), start=Decimal("0"))
    rows.sort(key=lambda e: e["total_outstanding"], reverse=True)
    return rows
