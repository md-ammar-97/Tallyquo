"""Builds a SupplyContext from already-fetched business_profile/client
rows -- kept separate from tax/loader.py's DB access so it stays trivially
testable with plain dicts, no session required."""

from datetime import date
from decimal import Decimal

from tallyquo.tax.engine import LineItem, SupplyContext, TaxTreatment


def build_supply_context(
    *,
    business_profile: dict,
    client: dict,
    line_amounts: list[tuple[Decimal, bool]],  # (amount, is_taxable)
    invoice_date: date,
    has_non_residency_evidence: bool,
    include_provincial_sales_tax: bool = False,
) -> SupplyContext:
    override = None
    if client.get("treatment_override_reason"):
        # X19: an override reason on the client record means the user made
        # a deliberate, audited choice -- respect it instead of re-deriving.
        override = TaxTreatment(client["tax_treatment"])

    return SupplyContext(
        supplier_registration_status=business_profile["registration_status"],
        supplier_registration_effective_date=business_profile.get("registration_effective_date"),
        recipient_country=client["country_code"],
        recipient_region=client.get("region_code"),
        recipient_is_gst_registered=client.get("is_gst_registered"),
        recipient_has_non_residency_evidence=has_non_residency_evidence,
        invoice_date=invoice_date,
        line_items=tuple(LineItem(amount=amt, is_taxable=taxable) for amt, taxable in line_amounts),
        treatment_override=override,
        include_provincial_sales_tax=include_provincial_sales_tax,
    )
