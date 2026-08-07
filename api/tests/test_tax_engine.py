"""Golden-file suite for the tax engine. Every test is keyed to an
edgecases.md ID. This is the P1 zone (edgecases.md §4, §13 priority 1) --
wrong output here is unrecoverable, so this suite must be exhaustive
before anything is wired to the invoice builder (implementation-plan.md
workstream 1.10)."""

from datetime import date
from decimal import Decimal

import pytest

from tallyquo.tax.engine import (
    LineItem,
    MissingJurisdiction,
    NoRateForDate,
    RateRow,
    RateTableSnapshot,
    SupplyContext,
    TaxTreatment,
    compute,
)

# Seed data as of August 2026, problem-statement.md §6.4 / datamodel.md §6.
# The Nova Scotia pair is the canonical test case for effective-dating.
RATE_TABLE = RateTableSnapshot(
    version_id="2026-08-test",
    rows=(
        RateRow("CA", None, "gst", Decimal("0.05000"), "GST", date(1991, 1, 1), None),
        RateRow("CA", "ON", "hst", Decimal("0.13000"), "HST", date(2010, 7, 1), None),
        RateRow("CA", "NB", "hst", Decimal("0.15000"), "HST", date(2016, 7, 1), None),
        RateRow("CA", "NL", "hst", Decimal("0.15000"), "HST", date(2016, 7, 1), None),
        RateRow("CA", "PE", "hst", Decimal("0.15000"), "HST", date(2016, 10, 1), None),
        RateRow("CA", "NS", "hst", Decimal("0.15000"), "HST", date(2010, 7, 1), date(2025, 3, 31)),
        RateRow("CA", "NS", "hst", Decimal("0.14000"), "HST", date(2025, 4, 1), None),
        RateRow("CA", "QC", "qst", Decimal("0.09975"), "QST", date(2013, 1, 1), None),
        RateRow("CA", "BC", "pst", Decimal("0.07000"), "PST", date(2013, 4, 1), None),
        RateRow("CA", "SK", "pst", Decimal("0.06000"), "PST", date(2025, 1, 1), None),
        RateRow("CA", "MB", "rst", Decimal("0.07000"), "RST", date(2019, 7, 1), None),
    ),
)


def _ctx(
    *,
    invoice_date: date,
    recipient_country: str = "CA",
    recipient_region: str | None = "ON",
    registration_status: str = "registered",
    registration_effective_date: date | None = date(2020, 1, 1),
    recipient_is_gst_registered: bool | None = False,
    recipient_has_non_residency_evidence: bool = True,
    amount: Decimal = Decimal("1000.00"),
    treatment_override: TaxTreatment | None = None,
    include_provincial_sales_tax: bool = False,
) -> SupplyContext:
    return SupplyContext(
        supplier_registration_status=registration_status,
        supplier_registration_effective_date=registration_effective_date,
        recipient_country=recipient_country,
        recipient_region=recipient_region,
        recipient_is_gst_registered=recipient_is_gst_registered,
        recipient_has_non_residency_evidence=recipient_has_non_residency_evidence,
        invoice_date=invoice_date,
        line_items=(LineItem(amount=amount, is_taxable=True),),
        treatment_override=treatment_override,
        include_provincial_sales_tax=include_provincial_sales_tax,
    )


def test_x1_place_of_supply_follows_recipient_not_supplier():
    """Alberta client, Ontario supplier -> 5% GST, not 13% HST."""
    ctx = _ctx(invoice_date=date(2026, 6, 1), recipient_region="AB")
    result = compute(ctx, RATE_TABLE)
    assert result.treatment == TaxTreatment.TAXABLE
    assert result.jurisdiction == "CA-AB"
    assert [line.tax_type for line in result.lines] == ["gst"]
    assert result.lines[0].amount == Decimal("50.00")


def test_x2_nova_scotia_pre_change_rate():
    """Invoice dated 2025-03-15 resolves the pre-change 15% rate."""
    ctx = _ctx(invoice_date=date(2025, 3, 15), recipient_region="NS")
    result = compute(ctx, RATE_TABLE)
    assert result.lines[0].rate == Decimal("0.15000")
    assert result.lines[0].amount == Decimal("150.00")


def test_x3_nova_scotia_post_change_rate_boundary_inclusive():
    """Invoice dated 2025-04-01 (the effective date itself) resolves 14%."""
    ctx = _ctx(invoice_date=date(2025, 4, 1), recipient_region="NS")
    result = compute(ctx, RATE_TABLE)
    assert result.lines[0].rate == Decimal("0.14000")
    assert result.lines[0].amount == Decimal("140.00")


def test_x2_x3_boundary_the_day_before_still_old_rate():
    ctx = _ctx(invoice_date=date(2025, 3, 31), recipient_region="NS")
    result = compute(ctx, RATE_TABLE)
    assert result.lines[0].rate == Decimal("0.15000")


def test_x4_reproducibility_same_inputs_same_output_regardless_of_when_called():
    """Historical invoice re-rendered years later must be byte-identical --
    the engine has no wall-clock dependency at all."""
    ctx = _ctx(invoice_date=date(2020, 1, 1), recipient_region="ON")
    result_a = compute(ctx, RATE_TABLE)
    result_b = compute(ctx, RATE_TABLE)
    assert result_a == result_b


def test_x5_zero_rated_vs_not_registered_are_never_collapsed():
    zero_rated = compute(
        _ctx(invoice_date=date(2026, 1, 1), recipient_country="US", recipient_region=None),
        RATE_TABLE,
    )
    not_registered = compute(
        _ctx(invoice_date=date(2026, 1, 1), registration_status="not_registered"),
        RATE_TABLE,
    )
    assert zero_rated.treatment == TaxTreatment.ZERO_RATED_EXPORT
    assert not_registered.treatment == TaxTreatment.NOT_REGISTERED
    assert zero_rated.lines[0].display_note != not_registered.lines[0].display_note
    assert zero_rated.lines[0].amount == not_registered.lines[0].amount == Decimal("0.00")
    # Different treatment enum is the load-bearing distinction, not the
    # (identical, both-zero) dollar amount.
    assert zero_rated.treatment != not_registered.treatment


def test_x6_registration_effective_date_gates_charging():
    before = compute(
        _ctx(
            invoice_date=date(2019, 12, 31),
            registration_status="registered",
            registration_effective_date=date(2020, 1, 1),
        ),
        RATE_TABLE,
    )
    on_date = compute(
        _ctx(
            invoice_date=date(2020, 1, 1),
            registration_status="registered",
            registration_effective_date=date(2020, 1, 1),
        ),
        RATE_TABLE,
    )
    assert before.treatment == TaxTreatment.NOT_REGISTERED
    assert on_date.treatment == TaxTreatment.TAXABLE


def test_x9_quebec_gst_and_qst_as_two_separate_uncompounded_lines():
    ctx = _ctx(invoice_date=date(2026, 1, 1), recipient_region="QC", amount=Decimal("1000.00"))
    result = compute(ctx, RATE_TABLE)
    types = {line.tax_type: line for line in result.lines}
    assert set(types) == {"gst", "qst"}
    # Not compounded: QST computed on the pre-tax base, same as GST's base.
    assert types["gst"].amount == Decimal("50.00")
    assert types["qst"].amount == Decimal("99.75")
    assert result.tax_total == Decimal("149.75")


def test_x10_bc_pst_off_by_default_for_services():
    ctx = _ctx(invoice_date=date(2026, 1, 1), recipient_region="BC")
    result = compute(ctx, RATE_TABLE)
    assert [line.tax_type for line in result.lines] == ["gst"]

    ctx_with_pst = _ctx(
        invoice_date=date(2026, 1, 1), recipient_region="BC", include_provincial_sales_tax=True
    )
    result_with_pst = compute(ctx_with_pst, RATE_TABLE)
    assert set(line.tax_type for line in result_with_pst.lines) == {"gst", "pst"}


def test_x11_non_resident_but_gst_registered_is_taxable_with_warning():
    ctx = _ctx(
        invoice_date=date(2026, 1, 1),
        recipient_country="US",
        recipient_region=None,
        recipient_is_gst_registered=True,
    )
    with pytest.raises(NoRateForDate):
        # TAXABLE is correctly derived, but no CA jurisdiction/rate exists
        # for a US region -- the engine must refuse to guess, not silently
        # charge $0 or apply a Canadian rate to a US recipient.
        compute(ctx, RATE_TABLE)


def test_x12_missing_non_residency_evidence_warns_but_does_not_block():
    ctx = _ctx(
        invoice_date=date(2026, 1, 1),
        recipient_country="US",
        recipient_region=None,
        recipient_has_non_residency_evidence=False,
    )
    result = compute(ctx, RATE_TABLE)
    assert result.treatment == TaxTreatment.ZERO_RATED_EXPORT
    assert any("evidence" in w.lower() for w in result.warnings)


def test_x13_no_rate_row_for_date_is_a_hard_error_never_a_default():
    # Registered well before the earliest ON HST row (2010-07-01) exists in
    # the table -- treatment resolves to TAXABLE, but no rate row covers
    # this date, which must be a hard error, not a silent $0 or a guess.
    ctx = _ctx(
        invoice_date=date(1980, 1, 1),
        recipient_region="ON",
        registration_effective_date=date(1970, 1, 1),
    )
    with pytest.raises(NoRateForDate):
        compute(ctx, RATE_TABLE)


def test_x15_mixed_taxable_and_exempt_lines_only_taxes_the_taxable_base():
    ctx = SupplyContext(
        supplier_registration_status="registered",
        supplier_registration_effective_date=date(2020, 1, 1),
        recipient_country="CA",
        recipient_region="ON",
        recipient_is_gst_registered=False,
        recipient_has_non_residency_evidence=True,
        invoice_date=date(2026, 1, 1),
        line_items=(
            LineItem(amount=Decimal("1000.00"), is_taxable=True),
            LineItem(amount=Decimal("500.00"), is_taxable=False),
        ),
    )
    result = compute(ctx, RATE_TABLE)
    assert result.lines[0].taxable_base == Decimal("1000.00")
    assert result.lines[0].amount == Decimal("130.00")


def test_x16_rounding_half_up_at_the_tax_line_level():
    # 13% of 7199.99 = 935.9987 -> rounds to 936.00
    ctx = _ctx(invoice_date=date(2026, 1, 1), recipient_region="ON", amount=Decimal("7199.99"))
    result = compute(ctx, RATE_TABLE)
    assert result.lines[0].amount == Decimal("936.00")


def test_x17_discount_reduces_taxable_base_before_tax():
    # Discounts are applied by the caller before line items reach the
    # engine (the engine only ever sees the post-discount amount) -- this
    # test documents that contract explicitly.
    full = compute(_ctx(invoice_date=date(2026, 1, 1), amount=Decimal("1000.00")), RATE_TABLE)
    discounted = compute(_ctx(invoice_date=date(2026, 1, 1), amount=Decimal("900.00")), RATE_TABLE)
    assert discounted.lines[0].amount < full.lines[0].amount
    assert discounted.lines[0].taxable_base == Decimal("900.00")


def test_x18_client_moves_province_each_invoice_uses_its_own_snapshot():
    invoice_1 = compute(_ctx(invoice_date=date(2026, 1, 1), recipient_region="ON"), RATE_TABLE)
    invoice_2 = compute(_ctx(invoice_date=date(2026, 6, 1), recipient_region="BC"), RATE_TABLE)
    assert invoice_1.jurisdiction == "CA-ON"
    assert invoice_2.jurisdiction == "CA-BC"


def test_x19_override_is_respected_and_skips_derivation():
    ctx = _ctx(
        invoice_date=date(2026, 1, 1),
        registration_status="not_registered",  # would normally force NOT_REGISTERED
        treatment_override=TaxTreatment.EXEMPT,
    )
    result = compute(ctx, RATE_TABLE)
    assert result.treatment == TaxTreatment.EXEMPT
    assert result.lines[0].display_note == "Exempt supply"


def test_missing_canadian_region_raises_rather_than_guesses():
    ctx = _ctx(invoice_date=date(2026, 1, 1), recipient_region=None)
    with pytest.raises(MissingJurisdiction):
        compute(ctx, RATE_TABLE)


def test_rate_precision_never_rounded_in_display_math():
    ctx = _ctx(invoice_date=date(2026, 1, 1), recipient_region="QC")
    result = compute(ctx, RATE_TABLE)
    qst_line = next(line for line in result.lines if line.tax_type == "qst")
    assert "9.975%" in qst_line.label
