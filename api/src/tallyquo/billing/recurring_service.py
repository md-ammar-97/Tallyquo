"""Recurring invoice rules + the generation job. datamodel.md §8,
edgecases.md R1-R12, implementation_plan.md workstreams 2.6-2.7.

The generation job (`generate_due_occurrences`) scans across all tenants
the same way `tax/snapshot_verify.py` does: an admin-level connection to
find who's due, then a `tenant_session()` per tenant for the actual
writes, so RLS stays intact even though the job itself has no single
tenant of its own (architecture.md §9: "All jobs ... run inside a
tenant context").
"""

import calendar
import json
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import invoices_service
from tallyquo.core.db import raw_session
from tallyquo.core.logging import get_logger
from tallyquo.core.tenant_context import tenant_session

logger = get_logger(__name__)

_CADENCE_MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}
_CADENCE_DAYS = {"weekly": 7, "biweekly": 14}

_COLUMNS = (
    "id, tenant_id, client_id, source_invoice_id, cadence, day_of_period, "
    "next_run_date, end_date, occurrences_remaining, auto_issue, is_paused, "
    "last_run_date, created_at"
)


def next_occurrence(cadence: str, day_of_period: int | None, from_date: date) -> date:
    """R1/R2: monthly+ cadences clamp to the target month's actual last day
    (the 31st in a 30-day month becomes the 30th; Feb 29 in a non-leap year
    becomes Feb 28) rather than overflowing into the next month."""
    if cadence in _CADENCE_DAYS:
        return from_date + timedelta(days=_CADENCE_DAYS[cadence])

    months = _CADENCE_MONTHS[cadence]
    total_months = from_date.month - 1 + months
    year = from_date.year + total_months // 12
    month = total_months % 12 + 1
    day = day_of_period or from_date.day
    last_day_of_month = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day_of_month))


# ---- CRUD -----------------------------------------------------------

async def create_rule(session: AsyncSession, tenant_id: UUID, data: dict) -> dict:
    rule_id = uuid4()
    columns = [*data.keys(), "id", "tenant_id"]
    placeholders = ", ".join(f":{c}" for c in columns)
    await session.execute(
        text(f"INSERT INTO recurring_rule ({', '.join(columns)}) VALUES ({placeholders})"),
        {**data, "id": rule_id, "tenant_id": tenant_id},
    )
    return await get_rule(session, rule_id)  # type: ignore[return-value]


async def get_rule(session: AsyncSession, rule_id: UUID) -> dict | None:
    result = await session.execute(text(f"SELECT {_COLUMNS} FROM recurring_rule WHERE id = :id"), {"id": rule_id})
    row = result.mappings().first()
    return dict(row) if row else None


async def list_rules(session: AsyncSession) -> list[dict]:
    cols = ", ".join(f"rr.{c}" for c in _COLUMNS.split(", "))
    result = await session.execute(
        text(
            f"SELECT {cols}, c.legal_name AS client_name FROM recurring_rule rr "
            "JOIN client c ON c.id = rr.client_id ORDER BY rr.next_run_date"
        )
    )
    return [dict(r) for r in result.mappings().all()]


async def update_rule(session: AsyncSession, rule_id: UUID, data: dict) -> dict | None:
    if not data:
        return await get_rule(session, rule_id)
    set_clause = ", ".join(f"{c} = :{c}" for c in data)
    result = await session.execute(
        text(f"UPDATE recurring_rule SET {set_clause} WHERE id = :id"), {**data, "id": rule_id}
    )
    if result.rowcount == 0:
        return None
    return await get_rule(session, rule_id)


async def skip_next(session: AsyncSession, tenant_id: UUID, rule_id: UUID) -> dict | None:
    rule = await get_rule(session, rule_id)
    if rule is None:
        return None
    new_next = next_occurrence(rule["cadence"], rule["day_of_period"], rule["next_run_date"])
    await session.execute(
        text(
            "INSERT INTO recurring_run (id, tenant_id, rule_id, occurrence_date, outcome, detail) "
            "VALUES (:id, :tenant_id, :rule_id, :occurrence_date, 'skipped', 'Skipped by user')"
        ),
        {"id": uuid4(), "tenant_id": tenant_id, "rule_id": rule_id, "occurrence_date": rule["next_run_date"]},
    )
    return await update_rule(session, rule_id, {"next_run_date": new_next})


async def resume_rule(session: AsyncSession, rule_id: UUID) -> dict | None:
    # R10: resumes from the next scheduled occurrence; skipped periods are
    # not backfilled unless the user explicitly requests it (not built --
    # no request for that beyond this default came up in the spec).
    rule = await get_rule(session, rule_id)
    if rule is None:
        return None
    next_run = rule["next_run_date"]
    today = date.today()
    while next_run < today:
        next_run = next_occurrence(rule["cadence"], rule["day_of_period"], next_run)
    return await update_rule(session, rule_id, {"is_paused": False, "next_run_date": next_run})


# ---- generation -------------------------------------------------------

async def _copy_line_items(session: AsyncSession, source_invoice_id: UUID | None) -> list[dict]:
    if source_invoice_id is None:
        return []
    source = await invoices_service.get_invoice(session, source_invoice_id)
    if source is None:
        return []
    return [
        {
            "description": li["description"],
            "quantity": li["quantity"],
            "unit": li["unit"],
            "unit_rate": li["unit_rate"],
            "amount": li["amount"],
            "is_taxable": li["is_taxable"],
            "project_ref": li["project_ref"],
        }
        for li in source["line_items"]
    ]


async def _generate_one(session: AsyncSession, rule: dict, occurrence_date: date) -> tuple[UUID, str, str | None]:
    """Returns (invoice_id, outcome, detail). Never raises for a compliance
    failure -- R8/P1: auto-issue always falls back to draft rather than
    propagating."""
    line_items = await _copy_line_items(session, rule["source_invoice_id"])
    source = (
        await invoices_service.get_invoice(session, rule["source_invoice_id"])
        if rule["source_invoice_id"]
        else None
    )

    # problem-statement.md §6.8: "Automatic rebuild of the service period
    # and invoice date per occurrence" -- shift the period by the same
    # offset the invoice date itself shifted, preserving its length.
    service_start = service_end = None
    if source and source.get("service_period_start") and source.get("service_period_end") and source.get("invoice_date"):
        shift = occurrence_date - source["invoice_date"]
        service_start = source["service_period_start"] + shift
        service_end = source["service_period_end"] + shift

    draft = await invoices_service.create_draft(
        session,
        rule["tenant_id"],
        {
            "client_id": rule["client_id"],
            "invoice_date": occurrence_date,
            "service_period_start": service_start,
            "service_period_end": service_end,
            "currency": source["currency"] if source else "CAD",
            "po_reference": source["po_reference"] if source else None,
            "notes": source["notes"] if source else None,
            "line_items": line_items,
        },
    )

    outcome, detail = "created", None
    if rule["auto_issue"]:
        try:
            await invoices_service.issue_invoice(
                session, rule["tenant_id"], None, draft["id"], False, actor_kind="job"
            )
            detail = None
        except (invoices_service.ComplianceError, invoices_service.InvoiceNotDraft) as exc:
            # R8, P1: never auto-issue a non-compliant invoice -- falls
            # back to draft, which is exactly what already happened above.
            detail = f"auto-issue blocked, left as draft: {exc}"

    await session.execute(
        text(
            "INSERT INTO audit_log (tenant_id, actor_kind, action, entity_type, entity_id, after) "
            "VALUES (:tenant_id, 'job', 'invoice.recurring_generated', 'invoice', :entity_id, :after)"
        ),
        {
            "tenant_id": rule["tenant_id"],
            "entity_id": draft["id"],
            "after": json.dumps({"rule_id": str(rule["id"]), "occurrence_date": str(occurrence_date)}),
        },
    )
    return draft["id"], outcome, detail


async def _process_due_rule(session: AsyncSession, rule: dict, today_in_tz: date) -> None:
    while rule["next_run_date"] <= today_in_tz:
        occurrence_date = rule["next_run_date"]

        # R5: client archived while the rule is active -- auto-pause, notify
        # (notification itself is Phase 2's notifications module, not built;
        # the audit_log entry is the durable record in the meantime).
        client = (
            await session.execute(
                text("SELECT archived_at FROM client WHERE id = :id"), {"id": rule["client_id"]}
            )
        ).mappings().first()
        if client is None or client["archived_at"] is not None:
            await update_rule(session, rule["id"], {"is_paused": True})
            await session.execute(
                text(
                    "INSERT INTO recurring_run (id, tenant_id, rule_id, occurrence_date, outcome, detail) "
                    "VALUES (:id, :tenant_id, :rule_id, :occurrence_date, 'skipped', "
                    "'Client archived -- rule auto-paused')"
                ),
                {
                    "id": uuid4(),
                    "tenant_id": rule["tenant_id"],
                    "rule_id": rule["id"],
                    "occurrence_date": occurrence_date,
                },
            )
            return

        # R3, P1: idempotent on (rule_id, occurrence_date). ON CONFLICT DO
        # NOTHING makes a second invocation for the same occurrence a no-op
        # rather than a duplicate invoice, even under concurrent job runs.
        run_id = uuid4()
        inserted = await session.execute(
            text(
                "INSERT INTO recurring_run (id, tenant_id, rule_id, occurrence_date, outcome) "
                "VALUES (:id, :tenant_id, :rule_id, :occurrence_date, 'pending') "
                "ON CONFLICT (rule_id, occurrence_date) DO NOTHING"
            ),
            {"id": run_id, "tenant_id": rule["tenant_id"], "rule_id": rule["id"], "occurrence_date": occurrence_date},
        )

        if inserted.rowcount > 0:
            invoice_id, outcome, detail = await _generate_one(session, rule, occurrence_date)
            await session.execute(
                text(
                    "UPDATE recurring_run SET invoice_id = :invoice_id, outcome = :outcome, detail = :detail "
                    "WHERE id = :id"
                ),
                {"id": run_id, "invoice_id": invoice_id, "outcome": outcome, "detail": detail},
            )

        next_run = next_occurrence(rule["cadence"], rule["day_of_period"], occurrence_date)
        occurrences_remaining = rule["occurrences_remaining"]
        updates: dict = {"next_run_date": next_run, "last_run_date": occurrence_date}
        if occurrences_remaining is not None:
            occurrences_remaining -= 1
            updates["occurrences_remaining"] = occurrences_remaining

        # R9: reaching zero (or passing end_date) completes the rule --
        # archived via is_paused, never deleted, so history stays queryable.
        if (occurrences_remaining is not None and occurrences_remaining <= 0) or (
            rule["end_date"] is not None and next_run > rule["end_date"]
        ):
            updates["is_paused"] = True

        rule = await update_rule(session, rule["id"], updates)  # type: ignore[assignment]
        if rule["is_paused"]:
            return


async def generate_due_occurrences() -> int:
    """Entry point for the scheduled job. Returns the count of rules
    processed (not occurrences -- a single rule can generate several in
    one call via R4's backfill).

    `tenant` is the one table this can safely read cross-tenant from an
    unscoped connection -- it isn't itself tenant-scoped (there's no
    "tenant" a tenant row belongs to). Every other table here, including
    business_profile for the timezone lookup, is RLS-protected and must be
    read from inside that specific tenant's `tenant_session()`, exactly
    like `tax/snapshot_verify.py`'s cross-tenant scan.
    """
    async with raw_session() as session:
        tenant_result = await session.execute(text("SELECT id FROM tenant WHERE status = 'active'"))
        tenant_ids = [row[0] for row in tenant_result.all()]

    processed = 0
    for tenant_id in tenant_ids:
        async with tenant_session(tenant_id) as session:
            tz_row = (
                await session.execute(text("SELECT timezone FROM business_profile WHERE tenant_id = :t"), {"t": tenant_id})
            ).mappings().first()
            tz_name = tz_row["timezone"] if tz_row else "America/Toronto"
            try:
                today_in_tz = datetime.now(ZoneInfo(tz_name)).date()
            except ZoneInfoNotFoundError:
                today_in_tz = date.today()  # unknown tz name -- fall back rather than fail the whole job

            result = await session.execute(
                text(f"SELECT {_COLUMNS} FROM recurring_rule WHERE is_paused = false AND next_run_date <= :today"),
                {"today": today_in_tz},
            )
            due_rules = [dict(r) for r in result.mappings().all()]
            for rule in due_rules:
                await _process_due_rule(session, rule, today_in_tz)
                processed += 1

    logger.info("recurring_generation_complete", tenants_scanned=len(tenant_ids), rules_processed=processed)
    return processed


if __name__ == "__main__":
    import asyncio

    asyncio.run(generate_due_occurrences())
