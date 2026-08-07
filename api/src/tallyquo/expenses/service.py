"""Expenses: manual entry + receipt-derived. datamodel.md §8,
edgecases.md E1-E15, implementation_plan.md workstreams 2.8-2.11.

`itc_eligible` (E7/E8, P1) is computed and stored at write time, not
derived at read time the way invoice status is (L15) -- it's a fixed
historical fact anchored to expense_date vs. the business's
registration_effective_date as of when the expense happened. Nothing
about that answer changes as time passes, unlike an overdue check
against today's date, so there's no staleness risk in storing it.
"""

import json
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_COLUMNS = (
    "e.id, e.expense_date, e.vendor, e.description, e.category_id, "
    "c.name AS category_name, c.t2125_line, c.deductible_pct, c.is_capital, "
    "e.currency, e.amount_total, e.tax_amount, e.tax_type, e.amount_net, "
    "e.business_use_pct, e.itc_eligible, e.client_id, e.is_rebilled, "
    "e.rebilled_invoice_id, e.payment_method, e.source, e.ocr_confidence, "
    "e.created_at"
)
_FROM = "expense e LEFT JOIN expense_category c ON c.id = e.category_id"


async def list_categories(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        text(
            "SELECT id, name, t2125_line, deductible_pct, is_capital "
            "FROM expense_category WHERE archived_at IS NULL ORDER BY name"
        )
    )
    return [dict(r) for r in result.mappings().all()]


async def _compute_itc_eligible(
    session: AsyncSession, tenant_id: UUID, expense_date_: date, tax_amount: Decimal
) -> bool:
    if tax_amount <= 0:
        return False
    profile = (
        await session.execute(
            text(
                "SELECT registration_status, registration_effective_date "
                "FROM business_profile WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )
    ).mappings().first()
    if profile is None or profile["registration_status"] != "registered":
        return False
    effective = profile["registration_effective_date"]
    return effective is not None and expense_date_ >= effective


def closed_year_warning(expense_date_: date) -> str | None:
    # E15: soft warning only, not a hard gate -- there's no "filed" concept
    # in this product yet (that's Phase 3's year-end pack).
    if expense_date_.year < date.today().year:
        return f"This expense is dated in {expense_date_.year}, which may already be filed."
    return None


async def get_expense(session: AsyncSession, expense_id: UUID) -> dict | None:
    result = await session.execute(
        text(f"SELECT {_COLUMNS} FROM {_FROM} WHERE e.id = :id AND e.deleted_at IS NULL"),
        {"id": expense_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_expenses(
    session: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: UUID | None = None,
    client_id: UUID | None = None,
) -> list[dict]:
    where = ["e.deleted_at IS NULL"]
    params: dict = {}
    if date_from is not None:
        where.append("e.expense_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        where.append("e.expense_date <= :date_to")
        params["date_to"] = date_to
    if category_id is not None:
        where.append("e.category_id = :category_id")
        params["category_id"] = category_id
    if client_id is not None:
        where.append("e.client_id = :client_id")
        params["client_id"] = client_id

    result = await session.execute(
        text(
            f"SELECT {_COLUMNS} FROM {_FROM} WHERE {' AND '.join(where)} "
            "ORDER BY e.expense_date DESC, e.created_at DESC"
        ),
        params,
    )
    return [dict(r) for r in result.mappings().all()]


async def create_expense(
    session: AsyncSession, tenant_id: UUID, actor_id: UUID, data: dict, *, receipt_id: UUID | None = None
) -> dict:
    expense_id = uuid4()
    data["amount_net"] = data["amount_total"] - data["tax_amount"]
    data["itc_eligible"] = await _compute_itc_eligible(
        session, tenant_id, data["expense_date"], data["tax_amount"]
    )

    columns = [*data.keys(), "id", "tenant_id"]
    placeholders = ", ".join(f":{c}" for c in columns)
    await session.execute(
        text(f"INSERT INTO expense ({', '.join(columns)}) VALUES ({placeholders})"),
        {**data, "id": expense_id, "tenant_id": tenant_id},
    )

    if receipt_id is not None:
        await session.execute(
            text("UPDATE receipt SET expense_id = :expense_id WHERE id = :id"),
            {"id": receipt_id, "expense_id": expense_id},
        )

    await session.execute(
        text(
            "INSERT INTO audit_log (tenant_id, actor_user_id, actor_kind, action, "
            "entity_type, entity_id, after) "
            "VALUES (:tenant_id, :actor_id, 'user', 'expense.created', 'expense', :entity_id, :after)"
        ),
        {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "entity_id": expense_id,
            "after": json.dumps(
                {"amount_total": str(data["amount_total"]), "vendor": data.get("vendor")}
            ),
        },
    )
    return await get_expense(session, expense_id)  # type: ignore[return-value]


async def update_expense(session: AsyncSession, tenant_id: UUID, expense_id: UUID, data: dict) -> dict | None:
    existing = await get_expense(session, expense_id)
    if existing is None:
        return None

    merged_total = data.get("amount_total", existing["amount_total"])
    merged_tax = data.get("tax_amount", existing["tax_amount"])
    data["amount_net"] = merged_total - merged_tax
    merged_date = data.get("expense_date", existing["expense_date"])
    # E2: OCR/previous values never silently overwrite a user's correction --
    # this recomputes from whatever the caller submits, which for an edit is
    # by definition the user's latest word on the field.
    data["itc_eligible"] = await _compute_itc_eligible(session, tenant_id, merged_date, merged_tax)

    set_clause = ", ".join(f"{c} = :{c}" for c in data)
    await session.execute(
        text(f"UPDATE expense SET {set_clause} WHERE id = :id"), {**data, "id": expense_id}
    )
    return await get_expense(session, expense_id)


async def delete_expense(session: AsyncSession, expense_id: UUID) -> bool:
    result = await session.execute(
        text("UPDATE expense SET deleted_at = now() WHERE id = :id AND deleted_at IS NULL"),
        {"id": expense_id},
    )
    return result.rowcount > 0


async def mark_rebilled(
    session: AsyncSession, expense_id: UUID, invoice_id: UUID
) -> dict | None:
    # 2.11/E12: links the expense to the invoice it was billed through, so
    # a P&L export (2.14) can exclude it from net cost -- the client is
    # covering it, so it isn't a deduction against this business's income.
    result = await session.execute(
        text(
            "UPDATE expense SET is_rebilled = true, rebilled_invoice_id = :invoice_id "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": expense_id, "invoice_id": invoice_id},
    )
    if result.rowcount == 0:
        return None
    return await get_expense(session, expense_id)
