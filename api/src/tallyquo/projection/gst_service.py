"""GST/HST net-owing by filing period (3.7) and the small-supplier
threshold tracker (3.8). Both are quarterly-grained: filing periods
because that's the CRA default for a small business (this app doesn't
yet track an assigned filing frequency -- quarterly is the safe,
common default, never a guess at a MORE favourable one), and the
threshold because S1 defines it as a rolling four-consecutive-
calendar-quarter window.

P10: net-owing is never rendered as revenue -- "held for CRA" framing
lives in schemas.py/the frontend, but the shape returned here (collected
vs. claimable vs. net, never a single blended "income" figure) is what
makes that framing possible.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SMALL_SUPPLIER_THRESHOLD = Decimal("30000.00")


@dataclass(frozen=True)
class QuarterPeriod:
    year: int
    quarter: int  # 1-4

    @property
    def start(self) -> date:
        return date(self.year, (self.quarter - 1) * 3 + 1, 1)

    @property
    def end(self) -> date:
        if self.quarter == 4:
            return date(self.year, 12, 31)
        next_start = date(self.year, self.quarter * 3 + 1, 1)
        return next_start.replace(day=1) - _one_day()

    def __str__(self) -> str:
        return f"{self.year}-Q{self.quarter}"


def _one_day():
    from datetime import timedelta

    return timedelta(days=1)


def quarter_of(d: date) -> QuarterPeriod:
    return QuarterPeriod(d.year, (d.month - 1) // 3 + 1)


def rolling_four_quarters_ending(d: date) -> list[QuarterPeriod]:
    current = quarter_of(d)
    quarters = [current]
    y, q = current.year, current.quarter
    for _ in range(3):
        q -= 1
        if q == 0:
            q = 4
            y -= 1
        quarters.append(QuarterPeriod(y, q))
    return list(reversed(quarters))


@dataclass(frozen=True)
class QuarterNetOwing:
    period: QuarterPeriod
    collected: Decimal
    itcs_claimable: Decimal
    net_owing: Decimal


async def net_owing_for_quarter(session: AsyncSession, period: QuarterPeriod) -> QuarterNetOwing:
    collected_result = await session.execute(
        text(
            "SELECT COALESCE(sum(tl.amount), 0) AS collected "
            "FROM invoice_tax_line tl JOIN invoice i ON i.tenant_id = tl.tenant_id AND i.id = tl.invoice_id "
            "WHERE i.status NOT IN ('draft', 'cancelled') "
            "AND tl.tax_type IN ('gst', 'hst') "
            "AND i.invoice_date >= :start AND i.invoice_date <= :end"
        ),
        {"start": period.start, "end": period.end},
    )
    collected = collected_result.scalar_one()

    # itc_eligible is already the GST/HST-specific signal (expenses/
    # service.py's _compute_itc_eligible: tax_amount > 0 plus registration
    # status/date -- this app has no notion of a PST/QST ITC). e.tax_type
    # is a separate, optional categorization field left NULL on most
    # manually-entered expenses, so filtering on it here would silently
    # under-count real, eligible claims -- unlike invoice_tax_line.tax_type
    # above, which the tax engine always populates.
    itc_result = await session.execute(
        text(
            "SELECT COALESCE(sum(e.tax_amount), 0) AS claimable "
            "FROM expense e "
            "WHERE e.deleted_at IS NULL AND e.itc_eligible = true "
            "AND e.expense_date >= :start AND e.expense_date <= :end"
        ),
        {"start": period.start, "end": period.end},
    )
    claimable = itc_result.scalar_one()

    return QuarterNetOwing(
        period=period, collected=collected, itcs_claimable=claimable, net_owing=collected - claimable
    )


async def net_owing_by_quarter(session: AsyncSession, year: int) -> list[QuarterNetOwing]:
    return [await net_owing_for_quarter(session, QuarterPeriod(year, q)) for q in range(1, 5)]


@dataclass(frozen=True)
class ThresholdStatus:
    rolling_revenue: Decimal
    threshold: Decimal
    pct_of_threshold: Decimal
    window_start: date
    window_end: date
    escalation: str  # "ok" | "attention" | "overdue" (mirrors design.md §8.1's colour steps)


async def threshold_status(session: AsyncSession, as_of: date) -> ThresholdStatus:
    """S1: zero-rated exports count toward the threshold, so this sums
    every non-exempt issued invoice's pre-tax revenue -- 'taxable',
    'zero_rated_export', AND 'not_registered' (the whole point of the
    threshold is to catch revenue accumulated *before* registering).
    Only 'exempt' supplies and cancelled/draft invoices are excluded, and
    credit notes are netted out of whichever invoice they reference
    (S7) -- otherwise a credited invoice would keep counting its full
    original amount toward a threshold it may no longer actually be
    close to. FX-converted to CAD per invoice (fx_rate_to_cad) rather
    than restricted to currency='CAD' like the simpler P&L report --
    silently omitting foreign-currency revenue here would risk under-
    counting toward a threshold whose entire purpose is not to be
    under-counted; credit notes ride the same invoice's rate since they
    aren't independently FX-tracked."""
    quarters = rolling_four_quarters_ending(as_of)
    window_start, window_end = quarters[0].start, quarters[-1].end

    result = await session.execute(
        text(
            "SELECT COALESCE(sum("
            "  (i.subtotal - i.discount_amount) * COALESCE(i.fx_rate_to_cad, 1)"
            "), 0) AS gross_revenue, "
            "COALESCE((SELECT sum(cn.amount * COALESCE(i2.fx_rate_to_cad, 1)) "
            "          FROM credit_note cn JOIN invoice i2 ON i2.id = cn.invoice_id "
            "          WHERE i2.status NOT IN ('draft', 'cancelled') "
            "          AND i2.tax_treatment_snapshot IN ('taxable', 'zero_rated_export', 'not_registered') "
            "          AND i2.invoice_date >= :start AND i2.invoice_date <= :end), 0) AS credited "
            "FROM invoice i "
            "WHERE i.status NOT IN ('draft', 'cancelled') "
            "AND i.tax_treatment_snapshot IN ('taxable', 'zero_rated_export', 'not_registered') "
            "AND i.invoice_date >= :start AND i.invoice_date <= :end"
        ),
        {"start": window_start, "end": window_end},
    )
    row = result.one()
    revenue = row.gross_revenue - row.credited

    pct = (revenue / SMALL_SUPPLIER_THRESHOLD * 100).quantize(Decimal("0.1"))
    if pct >= 90:
        escalation = "overdue"
    elif pct >= 75:
        escalation = "attention"
    else:
        escalation = "ok"

    return ThresholdStatus(
        rolling_revenue=revenue,
        threshold=SMALL_SUPPLIER_THRESHOLD,
        pct_of_threshold=pct,
        window_start=window_start,
        window_end=window_end,
        escalation=escalation,
    )
