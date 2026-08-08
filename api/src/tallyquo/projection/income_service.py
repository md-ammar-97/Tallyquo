"""Net business income for the projection engine: actual (year-to-date),
derived (extrapolated), and declared (user-entered) modes.

Net income here means the same thing as reporting/service.py's P&L
net_income (subtotal - discount_amount, minus deductible expenses) --
this module doesn't recompute it differently, it just aggregates it
across a full calendar year instead of per-period rows, and adds the
forward-looking pieces P&L has no reason to have (extrapolation,
scheduled recurring revenue, declared targets).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class YtdActuals:
    income: Decimal
    expenses: Decimal
    net_income: Decimal
    days_elapsed: int


async def ytd_actuals(session: AsyncSession, year: int, as_of: date) -> YtdActuals:
    year_start = date(year, 1, 1)
    # as_of can be in a future year relative to `year` (e.g. viewing a
    # closed prior year in January) -- clamp the "elapsed" window to the
    # requested year's own boundaries rather than reading past year-end.
    window_end = min(as_of, date(year, 12, 31))
    days_elapsed = max(1, (window_end - year_start).days + 1)

    income_result = await session.execute(
        text(
            "SELECT COALESCE(sum(subtotal - discount_amount), 0) AS income "
            "FROM invoice "
            "WHERE status NOT IN ('draft', 'cancelled') AND currency = 'CAD' "
            "AND invoice_date >= :year_start AND invoice_date <= :window_end"
        ),
        {"year_start": year_start, "window_end": window_end},
    )
    income = income_result.scalar_one()

    expense_result = await session.execute(
        text(
            "SELECT COALESCE(sum("
            "  ROUND(COALESCE(e.amount_cad, e.amount_net) "
            "        * (COALESCE(c.deductible_pct, 100) / 100) "
            "        * (e.business_use_pct / 100), 2)"
            "), 0) AS expenses "
            "FROM expense e LEFT JOIN expense_category c ON c.id = e.category_id "
            "WHERE e.deleted_at IS NULL AND e.is_rebilled = false "
            "AND COALESCE(c.is_capital, false) = false "
            "AND e.expense_date >= :year_start AND e.expense_date <= :window_end"
        ),
        {"year_start": year_start, "window_end": window_end},
    )
    expenses = expense_result.scalar_one()

    return YtdActuals(
        income=income, expenses=expenses, net_income=income - expenses, days_elapsed=days_elapsed
    )


@dataclass(frozen=True)
class ScheduledRecurringIncome:
    amount: Decimal
    rule_count: int


async def scheduled_recurring_income(
    session: AsyncSession, from_date: date, to_date: date
) -> ScheduledRecurringIncome:
    """R-series rules (recurring.md 2.6): projects each active, non-paused
    rule's remaining occurrences between `from_date` and `to_date` using
    its source invoice's amount as the per-occurrence estimate -- a rate
    change mid-schedule isn't foreseeable, so this is necessarily an
    approximation, folded into the "derived" mode's low-confidence label
    rather than presented as fact."""
    result = await session.execute(
        text(
            "SELECT r.cadence, r.next_run_date, r.end_date, r.occurrences_remaining, "
            "       COALESCE(i.subtotal - i.discount_amount, 0) AS per_occurrence "
            "FROM recurring_rule r "
            "LEFT JOIN invoice i ON i.tenant_id = r.tenant_id AND i.id = r.source_invoice_id "
            "WHERE r.is_paused = false "
            "AND r.next_run_date <= :to_date "
            "AND (r.end_date IS NULL OR r.end_date >= :from_date)"
        ),
        {"from_date": from_date, "to_date": to_date},
    )
    rows = result.all()

    cadence_days = {
        "weekly": 7,
        "biweekly": 14,
        "monthly": 30,
        "quarterly": 91,
        "semiannual": 182,
        "annual": 365,
    }

    total = Decimal("0.00")
    rule_count = 0
    for row in rows:
        step = cadence_days.get(row.cadence, 30)
        window_end = min(to_date, row.end_date) if row.end_date else to_date
        span_days = (window_end - max(from_date, row.next_run_date)).days
        if span_days < 0:
            continue
        occurrences = span_days // step + 1
        if row.occurrences_remaining is not None:
            occurrences = min(occurrences, row.occurrences_remaining)
        if occurrences <= 0:
            continue
        total += row.per_occurrence * occurrences
        rule_count += 1

    return ScheduledRecurringIncome(amount=total, rule_count=rule_count)


@dataclass(frozen=True)
class DerivedProjection:
    extrapolated_annual_income: Decimal
    scheduled_recurring_income: Decimal
    projected_annual_income: Decimal
    is_low_confidence: bool
    method: str


LOW_CONFIDENCE_DAY_THRESHOLD = 90


async def derived_income_projection(
    session: AsyncSession, year: int, as_of: date
) -> DerivedProjection:
    """P1 (edgecases.md §12): straight-line extrapolation from year-to-date
    net income, clearly labelled low-confidence in the first ~90 days of
    the year -- there just isn't enough signal yet for a full-year
    straight-line to mean much. P2 acknowledges this can still mislead
    for seasonal/lumpy income even past 90 days; that's why declared
    mode (income_service below) exists as an equally-first-class
    alternative, not a fallback."""
    actuals = await ytd_actuals(session, year, as_of)
    days_in_year = 366 if _is_leap(year) else 365
    extrapolated = (actuals.net_income / actuals.days_elapsed) * days_in_year
    extrapolated = extrapolated.quantize(Decimal("0.01"))

    recurring = await scheduled_recurring_income(
        session, from_date=min(as_of, date(year, 12, 31)), to_date=date(year, 12, 31)
    )

    return DerivedProjection(
        extrapolated_annual_income=extrapolated,
        scheduled_recurring_income=recurring.amount,
        projected_annual_income=extrapolated + recurring.amount,
        is_low_confidence=actuals.days_elapsed < LOW_CONFIDENCE_DAY_THRESHOLD,
        method="straight_line_extrapolation",
    )


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


async def get_declared_income(session: AsyncSession, year: int) -> Decimal | None:
    result = await session.execute(
        text("SELECT declared_annual_income FROM income_declaration WHERE year = :year"),
        {"year": year},
    )
    row = result.first()
    return row.declared_annual_income if row else None


async def set_declared_income(
    session: AsyncSession, tenant_id: UUID, year: int, amount: Decimal
) -> None:
    await session.execute(
        text(
            "INSERT INTO income_declaration (tenant_id, year, declared_annual_income, updated_at) "
            "VALUES (:tenant_id, :year, :amount, now()) "
            "ON CONFLICT (tenant_id, year) DO UPDATE SET "
            "declared_annual_income = EXCLUDED.declared_annual_income, updated_at = now()"
        ),
        {"tenant_id": tenant_id, "year": year, "amount": amount},
    )
