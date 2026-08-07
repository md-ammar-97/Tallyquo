"""P&L (profit & loss). problem-statement.md §6.7/§6.11: "Simple P&L by
month/quarter/year, exportable." A deliberately simple accrual-basis
report -- income tax / CPP / instalment projection is Phase 3's
`reporting` scope (implementation_plan.md 3.1-3.9), not this.

edgecases.md E12: a rebilled expense's corresponding revenue is already
counted in `income` via the invoice line it was billed through, so it's
excluded from the expense side entirely here -- applying its category's
deductible_pct (e.g. 50% for meals) to a pass-through cost the client
reimbursed would show a net loss on a transaction that was actually
net-zero, which is the double-counting the edge case warns against.

E11: capital purchases are excluded from ordinary expense deduction
entirely (no CCA computation -- that's an accountant's job).

Income is `subtotal - discount_amount` (pre-tax), never the tax-inclusive
`total` -- collected GST/HST isn't revenue, it's money held for the CRA
(problem-statement.md §6.10: "held-for-CRA framing, never rendered as
revenue"). Restricted to currency = 'CAD' pending real FX conversion
(2.4): omitting a non-CAD invoice from this report is honest; folding
its foreign total in as if it were CAD would just be wrong.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GROUP_BY_OPTIONS = {"month", "quarter", "year"}


async def pnl_rows(session: AsyncSession, *, group_by: str = "month") -> list[dict]:
    if group_by not in GROUP_BY_OPTIONS:
        raise ValueError(f"group_by must be one of {sorted(GROUP_BY_OPTIONS)}")

    income_result = await session.execute(
        text(
            f"""
            SELECT date_trunc('{group_by}', invoice_date)::date AS period,
                   COALESCE(sum(subtotal - discount_amount), 0) AS income
            FROM invoice
            WHERE status NOT IN ('draft', 'cancelled') AND currency = 'CAD'
            GROUP BY 1
            """
        )
    )
    income_by_period: dict = {row.period: row.income for row in income_result.all()}

    expense_result = await session.execute(
        text(
            f"""
            SELECT date_trunc('{group_by}', e.expense_date)::date AS period,
                   COALESCE(sum(
                     ROUND(
                       COALESCE(e.amount_cad, e.amount_net)
                       * (COALESCE(c.deductible_pct, 100) / 100)
                       * (e.business_use_pct / 100),
                       2
                     )
                   ), 0) AS expenses
            FROM expense e LEFT JOIN expense_category c ON c.id = e.category_id
            WHERE e.deleted_at IS NULL AND e.is_rebilled = false
              AND COALESCE(c.is_capital, false) = false
            GROUP BY 1
            """
        )
    )
    expenses_by_period: dict = {row.period: row.expenses for row in expense_result.all()}

    periods = sorted(set(income_by_period) | set(expenses_by_period))
    rows = []
    for period in periods:
        income = income_by_period.get(period, 0)
        expenses = expenses_by_period.get(period, 0)
        rows.append({"period": period, "income": income, "expenses": expenses, "net_income": income - expenses})
    return rows
