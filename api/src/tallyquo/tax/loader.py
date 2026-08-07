"""Loads rate data from the DB into the engine's pure input shape. This is
the only place tax_rate rows touch I/O -- the engine itself never does."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.tax.engine import RateRow, RateTableSnapshot


async def load_rate_table(session: AsyncSession) -> RateTableSnapshot:
    # tax_rate is global and not RLS-protected (datamodel.md §10) -- any
    # session can read it regardless of tenant context. Loads every row
    # regardless of version; the EXCLUDE constraint guarantees at most one
    # row is effective for a given (jurisdiction, tax_type) on any date, so
    # the engine's own date filtering is sufficient -- no version filter
    # needed here.
    result = await session.execute(
        text(
            "SELECT country_code, region_code, tax_type, rate, label, "
            "effective_from, effective_to FROM tax_rate ORDER BY effective_from"
        )
    )
    rows = tuple(
        RateRow(
            country_code=row.country_code,
            region_code=row.region_code,
            tax_type=row.tax_type,
            rate=row.rate,
            label=row.label,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
        )
        for row in result.all()
    )

    version_result = await session.execute(
        text("SELECT id FROM tax_rate_version ORDER BY published_at DESC LIMIT 1")
    )
    version_row = version_result.first()
    version_id = str(version_row[0]) if version_row else "unversioned"

    return RateTableSnapshot(version_id=version_id, rows=rows)
