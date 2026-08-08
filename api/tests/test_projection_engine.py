"""Golden-file suite for the projection engine. P1 zone (edgecases.md
§12): wrong output here misleads a user about how much tax they'll
owe, which is exactly the harm P9 exists to prevent.

BRACKET_TABLE below is the real seeded 2026 federal + Ontario data
(migration 0016), reproduced here so the test stays self-contained and
doesn't require a DB. Expected totals are hand-computed and re-derived
in comments so a future rate change is easy to re-verify by hand.
"""

from datetime import date
from decimal import Decimal

import pytest

from tallyquo.projection.engine import (
    BracketRow,
    BracketTableSnapshot,
    CppParameters,
    NoBracketsForJurisdiction,
    compute_cpp,
    compute_marginal_tax,
    compute_set_aside,
)

AS_OF = date(2026, 6, 1)

FEDERAL_TABLE = BracketTableSnapshot(
    rows=(
        BracketRow("federal", Decimal("0"), Decimal("16452.00"), Decimal("0.00000"), date(2026, 1, 1), None),
        BracketRow("federal", Decimal("16452.00"), Decimal("58523.00"), Decimal("0.14000"), date(2026, 1, 1), None),
        BracketRow("federal", Decimal("58523.00"), Decimal("117045.00"), Decimal("0.20500"), date(2026, 1, 1), None),
        BracketRow("federal", Decimal("117045.00"), Decimal("181440.00"), Decimal("0.26000"), date(2026, 1, 1), None),
        BracketRow("federal", Decimal("181440.00"), Decimal("258482.00"), Decimal("0.29000"), date(2026, 1, 1), None),
        BracketRow("federal", Decimal("258482.00"), None, Decimal("0.33000"), date(2026, 1, 1), None),
    )
)

ON_TABLE = BracketTableSnapshot(
    rows=(
        BracketRow("ON", Decimal("0"), Decimal("12989.00"), Decimal("0.00000"), date(2026, 1, 1), None),
        BracketRow("ON", Decimal("12989.00"), Decimal("53891.00"), Decimal("0.05050"), date(2026, 1, 1), None),
        BracketRow("ON", Decimal("53891.00"), Decimal("107785.00"), Decimal("0.09150"), date(2026, 1, 1), None),
        BracketRow("ON", Decimal("107785.00"), Decimal("150000.00"), Decimal("0.11160"), date(2026, 1, 1), None),
        BracketRow("ON", Decimal("150000.00"), Decimal("220000.00"), Decimal("0.12160"), date(2026, 1, 1), None),
        BracketRow("ON", Decimal("220000.00"), None, Decimal("0.13160"), date(2026, 1, 1), None),
    )
)

CPP_2026 = CppParameters(
    basic_exemption=Decimal("3500.00"),
    ympe=Decimal("74600.00"),
    yampe=Decimal("85000.00"),
    employee_rate=Decimal("0.05950"),
    self_employed_rate=Decimal("0.11900"),
    cpp2_employee_rate=Decimal("0.04000"),
    cpp2_self_employed_rate=Decimal("0.08000"),
    effective_from=date(2026, 1, 1),
    effective_to=None,
)


def test_income_below_bpa_owes_zero_federal_tax():
    result = compute_marginal_tax(Decimal("10000"), "federal", FEDERAL_TABLE, AS_OF)
    assert result.total_tax == Decimal("0.00")


def test_income_exactly_at_bpa_owes_zero():
    result = compute_marginal_tax(Decimal("16452.00"), "federal", FEDERAL_TABLE, AS_OF)
    assert result.total_tax == Decimal("0.00")


def test_marginal_tax_multi_bracket_federal():
    # 16452-58523 @ 14%: 42071 * 0.14 = 5889.94
    # 58523-80000 @ 20.5%: 21477 * 0.205 = 4402.785 -> 4402.79 (half-up)
    result = compute_marginal_tax(Decimal("80000"), "federal", FEDERAL_TABLE, AS_OF)
    assert result.total_tax == Decimal("10292.73")
    assert len(result.bands) == 3  # the 0% BPA band, 14%, 20.5%
    assert result.bands[0].tax == Decimal("0.00")


def test_marginal_tax_multi_bracket_provincial():
    # 12989-53891 @ 5.05%: 40902 * 0.0505 = 2065.551 -> 2065.55
    # 53891-80000 @ 9.15%: 26109 * 0.0915 = 2388.9735 -> 2388.97
    result = compute_marginal_tax(Decimal("80000"), "ON", ON_TABLE, AS_OF)
    assert result.total_tax == Decimal("4454.52")


def test_top_bracket_is_unbounded():
    result = compute_marginal_tax(Decimal("500000"), "federal", FEDERAL_TABLE, AS_OF)
    top_band = result.bands[-1]
    assert top_band.income_to is None
    assert top_band.rate == Decimal("0.33000")


def test_negative_net_income_clamped_to_zero_tax():
    """P4: expenses exceeding revenue -- net loss, never a negative tax."""
    result = compute_marginal_tax(Decimal("-5000"), "federal", FEDERAL_TABLE, AS_OF)
    assert result.total_tax == Decimal("0.00")
    assert result.net_income == Decimal("0.00")


def test_unknown_jurisdiction_raises_rather_than_guessing():
    """X13's sibling: never fall back to a default bracket schedule."""
    with pytest.raises(NoBracketsForJurisdiction):
        compute_marginal_tax(Decimal("50000"), "QC", ON_TABLE, AS_OF)


def test_cpp_below_basic_exemption_owes_nothing():
    result = compute_cpp(Decimal("3000"), CPP_2026)
    assert result.total_contribution == Decimal("0.00")


def test_cpp_base_contribution_both_halves():
    # (30000 - 3500) * 0.119 = 26500 * 0.119 = 3153.50
    result = compute_cpp(Decimal("30000"), CPP_2026)
    assert result.pensionable_earnings == Decimal("26500.00")
    assert result.base_contribution == Decimal("3153.50")
    assert result.cpp2_contribution == Decimal("0.00")
    assert result.total_contribution == Decimal("3153.50")


def test_cpp_capped_at_ympe_ceiling():
    """P8: capped at the earnings ceiling -- income above YMPE doesn't
    increase the base contribution further (only CPP2 does, up to YAMPE)."""
    # Full base band: (74600 - 3500) * 0.119 = 71100 * 0.119 = 8460.90
    result = compute_cpp(Decimal("80000"), CPP_2026)
    assert result.pensionable_earnings == Decimal("71100.00")
    assert result.base_contribution == Decimal("8460.90")
    # CPP2 band: min(80000,85000) - 74600 = 5400 * 0.08 = 432.00
    assert result.cpp2_pensionable_earnings == Decimal("5400.00")
    assert result.cpp2_contribution == Decimal("432.00")
    assert result.total_contribution == Decimal("8892.90")


def test_cpp2_capped_at_yampe_ceiling():
    # CPP2 band fully saturated: (85000 - 74600) * 0.08 = 10400 * 0.08 = 832.00
    result = compute_cpp(Decimal("200000"), CPP_2026)
    assert result.cpp2_pensionable_earnings == Decimal("10400.00")
    assert result.cpp2_contribution == Decimal("832.00")
    # base contribution unchanged above YMPE
    assert result.base_contribution == Decimal("8460.90")


def test_cpp_negative_income_owes_nothing():
    result = compute_cpp(Decimal("-1000"), CPP_2026)
    assert result.total_contribution == Decimal("0.00")


def test_set_aside_combines_federal_provincial_and_cpp():
    # federal 10292.73 + ON 4454.52 + CPP 8892.90 = 23640.15
    # pct = 23640.15 / 80000 * 100 = 29.5501875 -> 29.6
    result = compute_set_aside(
        Decimal("80000"), "ON", FEDERAL_TABLE, ON_TABLE, CPP_2026, AS_OF
    )
    assert result.total_estimated_tax_and_cpp == Decimal("23640.15")
    assert result.recommended_set_aside_pct == Decimal("29.6")


def test_set_aside_negative_income_reports_clamped_net_income():
    """Regression: net_business_income must agree with the $0 tax/CPP
    total it's displayed next to -- a raw negative figure next to a $0
    set-aside is exactly the confusing, wrong-looking output P4 warns
    against, even though the tax math itself was already correct."""
    result = compute_set_aside(
        Decimal("-8333.33"), "ON", FEDERAL_TABLE, ON_TABLE, CPP_2026, AS_OF
    )
    assert result.net_business_income == Decimal("0.00")
    assert result.total_estimated_tax_and_cpp == Decimal("0.00")
    assert result.recommended_set_aside_pct == Decimal("0.00")


def test_set_aside_zero_income_is_zero_percent_not_division_error():
    """P4: net loss -> set-aside is $0 with a clean 0%, not a crash or
    a negative/undefined percentage."""
    result = compute_set_aside(
        Decimal("0"), "ON", FEDERAL_TABLE, ON_TABLE, CPP_2026, AS_OF
    )
    assert result.total_estimated_tax_and_cpp == Decimal("0.00")
    assert result.recommended_set_aside_pct == Decimal("0.00")
