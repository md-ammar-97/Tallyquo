"""Year-end accountant pack. Phase 3 workstream 3.11: a single zip
bundling everything an accountant needs to file -- invoice PDFs,
a T2125-mapped expense CSV, the receipt images behind those expenses,
a GST/HST filing-period summary, and a P&L, plus a short README
carrying the same "estimate, not tax advice" framing as the rest of
Phase 3.

Built synchronously within the request rather than as a queued async
job -- same reasoning as 3.10 (`projection/service.py`) and 2.3
(`rollup_service.py`): at the invoice/expense/receipt volumes a single
sole proprietor accumulates in a year, rendering a handful of PDFs and
zipping some images is a sub-second-to-few-second operation, not
something that needs a job queue this product doesn't otherwise have.
"the pack is ready" is the HTTP response, not a status to poll for.

PDFs are rendered on demand (invoices_service.render_pdf, ADR-005 --
the DB row is the source of truth, nothing is ever pre-rendered to
storage) exactly like a single-invoice PDF download; only the
*receipt images* are fetched from storage, since those genuinely are
stored binary objects with nothing to regenerate them from.
"""

import csv
import io
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import botocore.exceptions
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import invoices_service
from tallyquo.core import storage
from tallyquo.core.logging import get_logger
from tallyquo.expenses import service as expenses_service
from tallyquo.identity import profile_service
from tallyquo.projection import gst_service
from tallyquo.reporting import service as reporting_service

logger = get_logger(__name__)

YEAR_END_PACK_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days, per implementation_plan.md 3.11 --
# deliberately longer than the 5-minute default every other signed URL in
# this product uses (architecture.md §11): a year-end pack is meant to be
# handed to (or re-downloaded by) an accountant over the following days,
# not fetched once immediately after the API call that created it.


class YearEndPackError(Exception):
    pass


class NoBusinessProfile(YearEndPackError):
    pass


class PackStorageUnavailable(YearEndPackError):
    """Object storage rejected the upload or isn't configured at all --
    surfaced as a clean error rather than a raw 500, the same as any
    other external dependency this product treats as fallible
    (architecture.md §7's dependency table)."""


def _csv_bytes(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


async def _receipts_for_expenses(session: AsyncSession, expense_ids: list[UUID]) -> list[dict]:
    if not expense_ids:
        return []
    result = await session.execute(
        text(
            "SELECT id, expense_id, file_ref, mime_type FROM receipt "
            "WHERE expense_id = ANY(:expense_ids)"
        ),
        {"expense_ids": expense_ids},
    )
    return [dict(r) for r in result.mappings().all()]


async def build_year_end_pack(session: AsyncSession, tenant_id: UUID, year: int) -> bytes:
    profile = await profile_service.get_profile(session, tenant_id)
    if profile is None:
        raise NoBusinessProfile("Set up a business profile before exporting a year-end pack.")

    year_start, year_end = date(year, 1, 1), date(year, 12, 31)
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # -- invoice PDFs -----------------------------------------------
        invoices = await invoices_service.list_invoices(session, date_from=year_start, date_to=year_end)
        issued = [i for i in invoices if i["status"] not in ("draft", "cancelled")]
        for inv in issued:
            pdf_bytes = await invoices_service.render_pdf(session, tenant_id, inv["id"])
            if pdf_bytes is None:
                continue
            name = inv["number"] or str(inv["id"])
            zf.writestr(f"invoices/{name}.pdf", pdf_bytes)

        # -- expenses.csv (T2125-mapped, E-series already handles the mapping) --
        expenses = await expenses_service.list_expenses(session, date_from=year_start, date_to=year_end)
        zf.writestr(
            "expenses.csv",
            _csv_bytes(
                ["expense_date", "vendor", "category", "t2125_line", "amount_total", "tax_amount",
                 "amount_net", "business_use_pct", "itc_eligible", "is_rebilled"],
                [
                    [e["expense_date"], e["vendor"] or "", e["category_name"] or "", e["t2125_line"] or "",
                     e["amount_total"], e["tax_amount"], e["amount_net"], e["business_use_pct"],
                     e["itc_eligible"], e["is_rebilled"]]
                    for e in expenses
                ],
            ),
        )

        # -- receipt images behind this year's expenses ------------------
        receipts = await _receipts_for_expenses(session, [e["id"] for e in expenses])
        expense_by_id = {e["id"]: e for e in expenses}
        for r in receipts:
            try:
                content = storage.download(r["file_ref"])
            except Exception:
                # A missing/unreachable object shouldn't sink the whole
                # pack -- the CSV row for this expense is still present
                # and correct, only the image itself is absent.
                continue
            ext = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "application/pdf": "pdf"}.get(
                r["mime_type"], "bin"
            )
            expense = expense_by_id.get(r["expense_id"])
            label = expense["expense_date"].isoformat() if expense else "unlinked"
            zf.writestr(f"receipts/{label}-{r['id']}.{ext}", content)

        # -- GST/HST filing-period summary --------------------------------
        quarters = await gst_service.net_owing_by_quarter(session, year)
        zf.writestr(
            "gst_hst_summary.csv",
            _csv_bytes(
                ["period", "collected", "itcs_claimable", "net_owing"],
                [[str(q.period), q.collected, q.itcs_claimable, q.net_owing] for q in quarters],
            ),
        )

        # -- P&L -----------------------------------------------------------
        pnl = await reporting_service.pnl_rows(session, group_by="month")
        pnl_year = [row for row in pnl if row["period"].year == year]
        zf.writestr(
            "profit_and_loss.csv",
            _csv_bytes(
                ["period", "income", "expenses", "net_income"],
                [[row["period"], row["income"], row["expenses"], row["net_income"]] for row in pnl_year],
            ),
        )

        # -- README ----------------------------------------------------
        legal_name = profile.get("legal_name") or "(business profile not set)"
        generated_at = datetime.now(timezone.utc).isoformat()
        readme = (
            f"Year-end accountant pack -- {legal_name} -- {year}\n"
            f"Generated {generated_at}\n\n"
            "Contents:\n"
            "  invoices/            One PDF per issued invoice dated in this year.\n"
            "  expenses.csv         T2125-line-mapped expenses dated in this year.\n"
            "  receipts/            Receipt images for the expenses above, where uploaded.\n"
            "  gst_hst_summary.csv  GST/HST collected, ITCs claimable, and net owing by quarter.\n"
            "  profit_and_loss.csv  Monthly P&L for this year (accrual basis).\n\n"
            "This pack is a record of what was entered in Tallyquo -- it is not tax advice "
            "and has not been reviewed by an accountant. Figures reflect data as of the "
            "generation date above.\n"
        )
        zf.writestr("README.txt", readme.encode("utf-8"))

    return buf.getvalue()


async def create_year_end_pack_url(session: AsyncSession, tenant_id: UUID, year: int) -> dict:
    pack_bytes = await build_year_end_pack(session, tenant_id, year)
    try:
        key = storage.upload_generated(
            str(tenant_id), ["year-end-packs", f"{year}-{uuid4()}.zip"], pack_bytes, "application/zip"
        )
        url = storage.signed_url(key, ttl_seconds=YEAR_END_PACK_TTL_SECONDS)
    except (RuntimeError, botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as exc:
        # The client only ever sees the generic message below -- this is
        # the one place the real cause (bad credentials, network, bucket
        # policy) gets recorded at all, since converting to a clean
        # HTTPException upstream means Starlette never logs a traceback
        # for it (it's a handled exception, not a crash).
        logger.error("year_end_pack_storage_upload_failed", error=str(exc), error_type=type(exc).__name__)
        raise PackStorageUnavailable(
            "Could not save the year-end pack -- storage is temporarily unavailable. Try again shortly."
        ) from exc
    return {
        "url": url,
        "filename": f"tallyquo-year-end-{year}.zip",
        "expires_in_seconds": YEAR_END_PACK_TTL_SECONDS,
        "byte_size": len(pack_bytes),
    }
