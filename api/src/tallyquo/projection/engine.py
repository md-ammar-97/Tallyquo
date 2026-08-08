"""The projection engine: pure functions, no I/O (same discipline as
tax/engine.py, ADR-003). Reference-data loading and P&L aggregation
happen entirely outside this module.

This module never touches invoice-level tax computation (tax/engine.py
stays untouched and untouched-by) -- it consumes *already-computed*
net business income and produces an income tax + CPP estimate from it.

Every number this module returns is an ESTIMATE (P9, edgecases.md §12):
never phrased as a bill, always with visible assumptions. The engine
itself doesn't render copy -- schemas.py / the frontend own that -- but
the shape of what it returns (components, not just totals) is what
makes an honest rendering possible.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class BracketRow:
    jurisdiction: str
    income_from: Decimal
    income_to: Decimal | None
    rate: Decimal
    effective_from: date
    effective_to: date | None


@dataclass(frozen=True)
class BracketTableSnapshot:
    rows: tuple[BracketRow, ...]


@dataclass(frozen=True)
class CppParameters:
    basic_exemption: Decimal
    ympe: Decimal
    yampe: Decimal
    employee_rate: Decimal
    self_employed_rate: Decimal
    cpp2_employee_rate: Decimal
    cpp2_self_employed_rate: Decimal
    effective_from: date
    effective_to: date | None


class ProjectionEngineError(Exception):
    pass


class NoBracketsForJurisdiction(ProjectionEngineError):
    """X13's sibling for income tax: never guess a bracket schedule for a
    jurisdiction/date we have no data for -- surface "not supported" to
    the caller instead of silently using $0 tax."""


class NoCppParametersForDate(ProjectionEngineError):
    pass


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TaxBand:
    """One bracket's contribution to the total -- rendered as a component,
    never collapsed into just the final number (P8's "components shown,
    not just the total" applies here too, not only to CPP)."""

    income_from: Decimal
    income_to: Decimal | None
    rate: Decimal
    taxable_amount: Decimal
    tax: Decimal


@dataclass(frozen=True)
class MarginalTaxResult:
    jurisdiction: str
    net_income: Decimal
    bands: tuple[TaxBand, ...]
    total_tax: Decimal


def _brackets_for(
    table: BracketTableSnapshot, jurisdiction: str, as_of: date
) -> list[BracketRow]:
    rows = [
        r
        for r in table.rows
        if r.jurisdiction == jurisdiction
        and r.effective_from <= as_of
        and (r.effective_to is None or as_of <= r.effective_to)
    ]
    return sorted(rows, key=lambda r: r.income_from)


def compute_marginal_tax(
    net_income: Decimal,
    jurisdiction: str,
    table: BracketTableSnapshot,
    as_of: date,
) -> MarginalTaxResult:
    """Standard marginal-bracket calculation. `net_income` here is net
    BUSINESS income (P&L net_income), not personal net income after other
    deductions -- an intentional simplification stated once, on the
    set-aside block, not re-derived per caller (P9)."""
    if net_income < 0:
        net_income = Decimal("0.00")

    brackets = _brackets_for(table, jurisdiction, as_of)
    if not brackets:
        raise NoBracketsForJurisdiction(
            f"No income tax brackets for jurisdiction {jurisdiction!r} on {as_of} -- "
            "not yet supported rather than guessed (X13's sibling)."
        )

    bands: list[TaxBand] = []
    total = Decimal("0.00")
    for b in brackets:
        if net_income <= b.income_from:
            break
        upper = b.income_to if b.income_to is not None else net_income
        band_top = min(upper, net_income)
        taxable_amount = band_top - b.income_from
        if taxable_amount <= 0:
            continue
        tax = _round(taxable_amount * b.rate)
        bands.append(
            TaxBand(
                income_from=b.income_from,
                income_to=b.income_to,
                rate=b.rate,
                taxable_amount=taxable_amount,
                tax=tax,
            )
        )
        total += tax

    return MarginalTaxResult(
        jurisdiction=jurisdiction, net_income=net_income, bands=tuple(bands), total_tax=total
    )


@dataclass(frozen=True)
class CppResult:
    pensionable_earnings: Decimal  # net_income clamped to [0, YMPE]
    base_contribution: Decimal
    cpp2_pensionable_earnings: Decimal  # the slice between YMPE and YAMPE
    cpp2_contribution: Decimal
    total_contribution: Decimal


def compute_cpp(net_income: Decimal, params: CppParameters) -> CppResult:
    """Self-employed pays BOTH halves (P8) -- self_employed_rate is already
    2x the employee rate in the seeded data, not doubled here. Below the
    basic exemption, no contribution at all (not just a zero band)."""
    if net_income < 0:
        net_income = Decimal("0.00")

    contributory_ceiling = max(Decimal("0.00"), params.ympe - params.basic_exemption)
    contributory_earnings = max(Decimal("0.00"), net_income - params.basic_exemption)
    pensionable_earnings = min(contributory_earnings, contributory_ceiling)
    base_contribution = _round(pensionable_earnings * params.self_employed_rate)

    cpp2_ceiling = max(Decimal("0.00"), params.yampe - params.ympe)
    cpp2_earnings = max(Decimal("0.00"), min(net_income, params.yampe) - params.ympe)
    cpp2_pensionable_earnings = min(cpp2_earnings, cpp2_ceiling)
    cpp2_contribution = _round(cpp2_pensionable_earnings * params.cpp2_self_employed_rate)

    return CppResult(
        pensionable_earnings=pensionable_earnings,
        base_contribution=base_contribution,
        cpp2_pensionable_earnings=cpp2_pensionable_earnings,
        cpp2_contribution=cpp2_contribution,
        total_contribution=base_contribution + cpp2_contribution,
    )


@dataclass(frozen=True)
class SetAsideResult:
    net_business_income: Decimal
    federal_tax: MarginalTaxResult
    provincial_tax: MarginalTaxResult
    cpp: CppResult
    total_estimated_tax_and_cpp: Decimal
    recommended_set_aside_pct: Decimal


def compute_set_aside(
    net_income: Decimal,
    jurisdiction: str,
    federal_table: BracketTableSnapshot,
    provincial_table: BracketTableSnapshot,
    cpp_params: CppParameters,
    as_of: date,
) -> SetAsideResult:
    """P9: never "you owe", always a recommended set-aside. P4: expenses
    exceeding revenue means net_income <= 0, and every downstream figure
    (tax, CPP, set-aside) correctly falls out to zero rather than
    negative -- there's no special-case branch needed because the
    engine already clamps negative income to zero throughout."""
    federal = compute_marginal_tax(net_income, "federal", federal_table, as_of)
    provincial = compute_marginal_tax(net_income, jurisdiction, provincial_table, as_of)
    cpp = compute_cpp(net_income, cpp_params)

    # federal/provincial/cpp each clamp negative income to zero internally
    # (and correctly report $0 tax/CPP for a loss year) -- clamp here too
    # so the headline net_business_income figure agrees with them, rather
    # than surfacing the raw negative number next to a $0 tax total.
    clamped_income = max(Decimal("0.00"), net_income)

    total = federal.total_tax + provincial.total_tax + cpp.total_contribution
    pct = Decimal("0.00") if clamped_income <= 0 else (total / clamped_income * 100).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )

    return SetAsideResult(
        net_business_income=clamped_income,
        federal_tax=federal,
        provincial_tax=provincial,
        cpp=cpp,
        total_estimated_tax_and_cpp=total,
        recommended_set_aside_pct=pct,
    )
