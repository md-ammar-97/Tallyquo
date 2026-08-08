"""Loads income_tax_bracket / cpp_parameter rows from the DB into the
engine's pure input shapes. This is the only place those tables touch
I/O -- the engine itself never does (mirrors tax/loader.py exactly)."""

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.projection.engine import BracketRow, BracketTableSnapshot, CppParameters, NoCppParametersForDate


async def load_bracket_table(session: AsyncSession) -> BracketTableSnapshot:
    # income_tax_bracket is global and not RLS-protected (datamodel.md
    # §10) -- any session can read it regardless of tenant context.
    result = await session.execute(
        text(
            "SELECT jurisdiction, income_from, income_to, rate, "
            "effective_from, effective_to FROM income_tax_bracket "
            "ORDER BY jurisdiction, effective_from, income_from"
        )
    )
    rows = tuple(
        BracketRow(
            jurisdiction=row.jurisdiction,
            income_from=row.income_from,
            income_to=row.income_to,
            rate=row.rate,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
        )
        for row in result.all()
    )
    return BracketTableSnapshot(rows=rows)


async def load_cpp_parameters(session: AsyncSession, as_of: date) -> CppParameters:
    result = await session.execute(
        text(
            "SELECT basic_exemption, ympe, yampe, employee_rate, self_employed_rate, "
            "cpp2_employee_rate, cpp2_self_employed_rate, effective_from, effective_to "
            "FROM cpp_parameter "
            "WHERE effective_from <= :as_of AND (effective_to IS NULL OR effective_to >= :as_of) "
            "ORDER BY effective_from DESC LIMIT 1"
        ),
        {"as_of": as_of},
    )
    row = result.first()
    if row is None:
        raise NoCppParametersForDate(f"No CPP parameters effective on {as_of}.")
    return CppParameters(
        basic_exemption=row.basic_exemption,
        ympe=row.ympe,
        yampe=row.yampe,
        employee_rate=row.employee_rate,
        self_employed_rate=row.self_employed_rate,
        cpp2_employee_rate=row.cpp2_employee_rate,
        cpp2_self_employed_rate=row.cpp2_self_employed_rate,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
    )
