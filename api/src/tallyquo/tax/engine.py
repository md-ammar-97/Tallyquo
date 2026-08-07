"""The tax engine: a pure function, no I/O (ADR-003).

`compute(context, rate_table)` is the entire public surface. Rate loading
and persistence happen entirely outside this module. This purity is what
makes historical reproduction trivial (edgecases.md X4): feed it the
archived rate-table snapshot and the original invoice's context, get the
original answer, forever.

Every branch below is annotated with the edgecases.md ID it exists to
satisfy -- this file's test suite (tests/test_tax_engine.py) is a golden-
file suite keyed to those same IDs.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class TaxTreatment(StrEnum):
    NOT_REGISTERED = "not_registered"
    TAXABLE = "taxable"
    ZERO_RATED_EXPORT = "zero_rated_export"
    EXEMPT = "exempt"


@dataclass(frozen=True)
class RateRow:
    country_code: str
    region_code: str | None  # None = country-wide (federal GST)
    tax_type: str  # gst | hst | pst | qst | rst
    rate: Decimal
    label: str
    effective_from: date
    effective_to: date | None


@dataclass(frozen=True)
class RateTableSnapshot:
    version_id: str
    rows: tuple[RateRow, ...]


@dataclass(frozen=True)
class LineItem:
    amount: Decimal
    is_taxable: bool = True


@dataclass(frozen=True)
class SupplyContext:
    supplier_registration_status: str  # not_registered | registration_pending | registered
    supplier_registration_effective_date: date | None
    recipient_country: str
    recipient_region: str | None
    recipient_is_gst_registered: bool | None
    recipient_has_non_residency_evidence: bool
    invoice_date: date
    line_items: tuple[LineItem, ...]
    # X19: a typed override, stored on the client, respected here rather
    # than re-derived -- the derived value is right far more often than
    # the user's assumption, so this is a deliberate escape hatch, not
    # the default path.
    treatment_override: TaxTreatment | None = None
    # X10: PST/RST on services is narrower than GST -- most professional
    # services are PST-exempt in BC/SK/MB. Off by default; the caller
    # (invoice builder) exposes this as an explicit line-level choice.
    include_provincial_sales_tax: bool = False


@dataclass(frozen=True)
class TaxLine:
    tax_type: str | None
    label: str
    rate: Decimal | None
    taxable_base: Decimal
    amount: Decimal
    display_note: str | None = None


@dataclass(frozen=True)
class TaxResult:
    treatment: TaxTreatment
    jurisdiction: str | None  # "CA-ON", "US", or None for not_registered
    lines: tuple[TaxLine, ...]
    tax_total: Decimal
    warnings: tuple[str, ...]
    table_version: str


class TaxEngineError(Exception):
    pass


class NoRateForDate(TaxEngineError):
    """X13: never fall back to a default rate -- refuse to issue instead."""


class MissingJurisdiction(TaxEngineError):
    """A Canadian client with no region on file (D7 should have already
    blocked this at the client layer, but the engine never guesses)."""


def resolve_treatment(ctx: SupplyContext) -> tuple[TaxTreatment, list[str]]:
    """X1-X21 P1 zone. Order matters: registration gates everything else."""
    warnings: list[str] = []

    if ctx.treatment_override is not None:
        return ctx.treatment_override, warnings

    # X6, X7: registration status AND effective date, evaluated by
    # invoice_date -- never by "today".
    if ctx.supplier_registration_status != "registered":
        return TaxTreatment.NOT_REGISTERED, warnings
    if (
        ctx.supplier_registration_effective_date is None
        or ctx.invoice_date < ctx.supplier_registration_effective_date
    ):
        return TaxTreatment.NOT_REGISTERED, warnings

    if ctx.recipient_country != "CA":
        # X11, P1: a non-resident who IS GST/HST-registered is not the
        # simple zero-rated case -- most zero-rating provisions require
        # the recipient to be both non-resident AND unregistered.
        if ctx.recipient_is_gst_registered:
            warnings.append(
                "Recipient is a non-resident but GST/HST-registered -- most "
                "zero-rating provisions do not apply. Confirm jurisdiction "
                "manually rather than trusting this derived value."
            )
            return TaxTreatment.TAXABLE, warnings
        # X12: nag, never gate, on missing non-residency evidence.
        if not ctx.recipient_has_non_residency_evidence:
            warnings.append(
                "No non-residency evidence on file for this client "
                "(edgecases.md X12) -- the CRA places the burden of proof "
                "on the supplier."
            )
        return TaxTreatment.ZERO_RATED_EXPORT, warnings

    return TaxTreatment.TAXABLE, warnings


def resolve_jurisdiction(ctx: SupplyContext, treatment: TaxTreatment) -> str | None:
    """Place of supply is the RECIPIENT's location, never the supplier's
    (X1, P1) -- this is the single most common error in this segment."""
    if treatment == TaxTreatment.NOT_REGISTERED:
        return None
    if ctx.recipient_country != "CA":
        return ctx.recipient_country
    if not ctx.recipient_region:
        raise MissingJurisdiction("Canadian client is missing a region/province.")
    return f"CA-{ctx.recipient_region}"


def _taxable_base(ctx: SupplyContext) -> Decimal:
    # X15: the taxable base is the sum of taxable lines only.
    total = Decimal("0.00")
    for li in ctx.line_items:
        if li.is_taxable:
            total += li.amount
    return total


def _round(amount: Decimal) -> Decimal:
    # X16: round half-up to 2dp at the tax-LINE level, once, never per item.
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_rate(rate: Decimal) -> str:
    # design.md: true precision, "13%", "9.975%" -- never rounded to "10%".
    as_pct = (rate * 100).normalize()
    # normalize() can produce exponent notation (e.g. 1.3E+1) for whole
    # numbers -- render as a plain decimal string instead.
    text = format(as_pct, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}%"


def compute(ctx: SupplyContext, rate_table: RateTableSnapshot) -> TaxResult:
    treatment, warnings = resolve_treatment(ctx)
    jurisdiction = resolve_jurisdiction(ctx, treatment)
    base = _taxable_base(ctx)

    if treatment == TaxTreatment.NOT_REGISTERED:
        lines = (
            TaxLine(
                tax_type=None,
                label="GST/HST",
                rate=None,
                taxable_base=base,
                amount=Decimal("0.00"),
                display_note="Not charged -- supplier not yet registered",
            ),
        )
        return TaxResult(treatment, jurisdiction, lines, Decimal("0.00"), tuple(warnings), rate_table.version_id)

    if treatment == TaxTreatment.EXEMPT:
        lines = (
            TaxLine(
                tax_type=None,
                label="GST/HST",
                rate=None,
                taxable_base=base,
                amount=Decimal("0.00"),
                display_note="Exempt supply",
            ),
        )
        return TaxResult(treatment, jurisdiction, lines, Decimal("0.00"), tuple(warnings), rate_table.version_id)

    if treatment == TaxTreatment.ZERO_RATED_EXPORT:
        lines = (
            TaxLine(
                tax_type="gst",
                label="GST/HST -- 0% zero-rated supply",
                rate=Decimal("0.00000"),
                taxable_base=base,
                amount=Decimal("0.00"),
                display_note="zero-rated supply",
            ),
        )
        return TaxResult(treatment, jurisdiction, lines, Decimal("0.00"), tuple(warnings), rate_table.version_id)

    # TAXABLE from here down.
    if jurisdiction is None or not jurisdiction.startswith("CA-"):
        # X11's non-resident-but-registered case: no clean CA rate applies.
        # X13 forbids guessing a default, so this is a hard stop.
        raise NoRateForDate(
            f"No rate rule defined for jurisdiction {jurisdiction!r} -- refusing to guess (X13)."
        )

    region = jurisdiction.removeprefix("CA-")
    applicable = [
        r
        for r in rate_table.rows
        if r.country_code == "CA"
        and r.region_code == region
        and r.effective_from <= ctx.invoice_date
        and (r.effective_to is None or ctx.invoice_date <= r.effective_to)
    ]
    # Federal GST applies everywhere unless superseded by a province-wide
    # HST row (Ontario etc. store HST as the province's own row, not a
    # GST+something combination) -- pull in the federal row only when the
    # province doesn't have its own HST row covering this date.
    if not any(r.tax_type == "hst" for r in applicable):
        applicable += [
            r
            for r in rate_table.rows
            if r.country_code == "CA"
            and r.region_code is None
            and r.tax_type == "gst"
            and r.effective_from <= ctx.invoice_date
            and (r.effective_to is None or ctx.invoice_date <= r.effective_to)
        ]

    if not ctx.include_provincial_sales_tax:
        # X10: PST/RST off by default for services.
        applicable = [r for r in applicable if r.tax_type not in ("pst", "rst")]

    if not applicable:
        raise NoRateForDate(
            f"No rate table row for {jurisdiction} on {ctx.invoice_date} (X13)."
        )

    lines = []
    total = Decimal("0.00")
    for r in sorted(applicable, key=lambda x: x.tax_type):
        amt = _round(base * r.rate)
        label = f"{r.label} ({region}) -- {_format_rate(r.rate)}"
        lines.append(
            TaxLine(tax_type=r.tax_type, label=label, rate=r.rate, taxable_base=base, amount=amt)
        )
        total += amt

    return TaxResult(treatment, jurisdiction, tuple(lines), total, tuple(warnings), rate_table.version_id)
