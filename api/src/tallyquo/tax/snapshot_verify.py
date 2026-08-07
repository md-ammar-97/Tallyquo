"""Nightly integrity job (architecture.md §9, implementation-plan.md 1.24).

Recomputes every issued invoice's tax from its frozen snapshot (treatment,
jurisdiction, rate-table version, line amounts) and compares to the stored
figures. A mismatch means either a snapshot is corrupt or the tax engine
changed behaviour for historical input -- P1, alert immediately, never
silently accept the drift.

Deliberately does NOT re-derive treatment/jurisdiction from current client/
profile data -- that's exactly what freezing the snapshot at issue time
protects against (edgecases.md X4, X18). It re-applies the FROZEN
treatment and jurisdiction against the FROZEN rate-table version, which
tests "did the rate application and arithmetic stay correct", the thing
this job exists to catch.
"""

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.db import raw_session
from tallyquo.core.logging import get_logger
from tallyquo.core.tenant_context import tenant_session
from tallyquo.tax.engine import LineItem, RateRow, RateTableSnapshot, SupplyContext, TaxTreatment, compute

logger = get_logger(__name__)


@dataclass(frozen=True)
class MismatchReport:
    invoice_id: UUID
    tenant_id: UUID
    number: str | None
    stored_tax_total: Decimal
    recomputed_tax_total: Decimal


async def _load_rate_table_for_version(session: AsyncSession, version_id: UUID) -> RateTableSnapshot:
    result = await session.execute(
        text(
            "SELECT country_code, region_code, tax_type, rate, label, "
            "effective_from, effective_to FROM tax_rate WHERE version_id = :v"
        ),
        {"v": version_id},
    )
    rows = tuple(RateRow(**dict(row._mapping)) for row in result.all())
    return RateTableSnapshot(version_id=str(version_id), rows=rows)


async def verify_invoice(session: AsyncSession, invoice_row: dict) -> MismatchReport | None:
    if invoice_row["tax_version_id"] is None:
        return None  # not_registered / exempt / zero_rated -- no rate table involved

    treatment = TaxTreatment(invoice_row["tax_treatment_snapshot"])
    jurisdiction = invoice_row["tax_jurisdiction_snapshot"]
    if jurisdiction and jurisdiction.startswith("CA-"):
        country, region = "CA", jurisdiction.removeprefix("CA-")
    else:
        country, region = (jurisdiction or "US"), None

    lines_result = await session.execute(
        text("SELECT amount, is_taxable FROM invoice_line WHERE invoice_id = :id"),
        {"id": invoice_row["id"]},
    )
    line_items = tuple(
        LineItem(amount=row.amount, is_taxable=row.is_taxable) for row in lines_result.all()
    )

    ctx = SupplyContext(
        supplier_registration_status="registered",  # irrelevant: treatment_override short-circuits it
        supplier_registration_effective_date=None,
        recipient_country=country,
        recipient_region=region,
        recipient_is_gst_registered=None,
        recipient_has_non_residency_evidence=True,  # irrelevant: override skips this check too
        invoice_date=invoice_row["invoice_date"],
        line_items=line_items,
        treatment_override=treatment,
    )
    rate_table = await _load_rate_table_for_version(session, invoice_row["tax_version_id"])
    result = compute(ctx, rate_table)

    if result.tax_total != invoice_row["tax_total"]:
        return MismatchReport(
            invoice_id=invoice_row["id"],
            tenant_id=invoice_row["tenant_id"],
            number=invoice_row["number"],
            stored_tax_total=invoice_row["tax_total"],
            recomputed_tax_total=result.tax_total,
        )
    return None


async def run() -> list[MismatchReport]:
    mismatches: list[MismatchReport] = []
    async with raw_session() as session:
        tenant_result = await session.execute(text("SELECT id FROM tenant WHERE status = 'active'"))
        tenant_ids = [row[0] for row in tenant_result.all()]

    for tenant_id in tenant_ids:
        async with tenant_session(tenant_id) as session:
            result = await session.execute(
                text(
                    "SELECT id, tenant_id, number, invoice_date, tax_treatment_snapshot, "
                    "tax_jurisdiction_snapshot, tax_version_id, tax_total "
                    "FROM invoice WHERE status != 'draft'"
                )
            )
            for row in result.mappings().all():
                report = await verify_invoice(session, dict(row))
                if report is not None:
                    mismatches.append(report)
                    logger.error(
                        "tax_snapshot_mismatch",
                        invoice_id=str(report.invoice_id),
                        tenant_id=str(report.tenant_id),
                        number=report.number,
                        stored=str(report.stored_tax_total),
                        recomputed=str(report.recomputed_tax_total),
                    )

    logger.info("snapshot_verify_complete", invoices_checked_tenants=len(tenant_ids), mismatches=len(mismatches))
    return mismatches


if __name__ == "__main__":
    found = asyncio.run(run())
    if found:
        raise SystemExit(f"{len(found)} tax snapshot mismatch(es) found -- see logs above (P1)")
