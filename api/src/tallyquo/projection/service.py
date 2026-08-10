"""Orchestrates the full projection view: income (derived + declared),
set-aside recommendation (income tax + CPP), GST/HST net-owing, small-
supplier threshold, and the quarterly instalment warning.

Nothing here is a bill (P9). Every number is an estimate, and the
components behind it (which bracket, which quarter, which mode) are
always part of the response, never collapsed into a single opaque
figure -- that's what makes "expand to see assumptions" (design.md
§8.1) possible on the frontend without a second round trip.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.identity import profile_service
from tallyquo.projection import gst_service, income_service
from tallyquo.projection.engine import NoBracketsForJurisdiction, SetAsideResult, compute_set_aside
from tallyquo.projection.loader import load_bracket_table, load_cpp_parameters

QUARTERLY_INSTALMENT_THRESHOLD = Decimal("3000.00")


class ProjectionError(Exception):
    pass


class NoBusinessProfile(ProjectionError):
    pass


class JurisdictionNotSupported(ProjectionError):
    pass


@dataclass(frozen=True)
class IncomeView:
    mode: str  # "derived" | "declared"
    derived: income_service.DerivedProjection
    declared_annual_income: Decimal | None
    active_projected_income: Decimal
    variance_from_derived: Decimal | None  # declared - derived, when both present (P3)


@dataclass(frozen=True)
class InstalmentWarning:
    applies: bool
    projected_net_tax_owing: Decimal
    threshold: Decimal


@dataclass(frozen=True)
class ProjectionView:
    year: int
    as_of: date
    jurisdiction: str
    income: IncomeView
    set_aside: SetAsideResult
    quarterly_net_owing: list[gst_service.QuarterNetOwing]
    threshold: gst_service.ThresholdStatus
    instalment_warning: InstalmentWarning
    ytd: income_service.YtdActuals


async def build_projection(
    session: AsyncSession, tenant_id: UUID, *, year: int | None = None, as_of: date | None = None
) -> ProjectionView:
    as_of = as_of or date.today()
    year = year or as_of.year

    profile = await profile_service.get_profile(session, tenant_id)
    if profile is None:
        raise NoBusinessProfile("Set up a business profile before viewing projections.")
    jurisdiction = profile["region_code"]

    derived = await income_service.derived_income_projection(session, year, as_of)
    declared = await income_service.get_declared_income(session, year)

    if declared is not None:
        mode = "declared"
        active_income = declared
        variance = declared - derived.projected_annual_income
    else:
        mode = "derived"
        active_income = derived.projected_annual_income
        variance = None

    income_view = IncomeView(
        mode=mode,
        derived=derived,
        declared_annual_income=declared,
        active_projected_income=active_income,
        variance_from_derived=variance,
    )

    # load_bracket_table returns every jurisdiction's rows in one snapshot;
    # compute_marginal_tax filters it by whichever jurisdiction string it's
    # asked for, so the same snapshot is passed for both the federal and
    # provincial slices below rather than fetching two separate tables.
    bracket_table = await load_bracket_table(session)
    cpp_params = await load_cpp_parameters(session, as_of)

    try:
        set_aside = compute_set_aside(
            active_income, jurisdiction, bracket_table, bracket_table, cpp_params, as_of
        )
    except NoBracketsForJurisdiction as exc:
        raise JurisdictionNotSupported(
            f"Income tax projection isn't available for jurisdiction {jurisdiction!r} yet."
        ) from exc

    quarterly = await gst_service.net_owing_by_quarter(session, year)
    threshold = await gst_service.threshold_status(session, as_of)

    # Redesigned dashboard's "Total Invoiced"/"Estimated Expenses" tiles.
    # derived_income_projection() above already computes this internally
    # (it's the ratio behind the straight-line extrapolation) but only
    # returns the extrapolated figure, not the raw actuals -- fetched
    # again here rather than widening that function's return contract.
    ytd = await income_service.ytd_actuals(session, year, as_of)

    # CRA's instalment threshold is about *net income tax* owing (income
    # tax + CPP, both settled on the same T1 return) -- GST/HST net-owing
    # is a wholly separate remittance with its own return (GST34) and its
    # own mechanics, so it deliberately does NOT get added in here even
    # though both numbers are "money set aside for the CRA" in spirit.
    projected_net_tax_owing = set_aside.total_estimated_tax_and_cpp
    instalment = InstalmentWarning(
        applies=projected_net_tax_owing > QUARTERLY_INSTALMENT_THRESHOLD,
        projected_net_tax_owing=projected_net_tax_owing,
        threshold=QUARTERLY_INSTALMENT_THRESHOLD,
    )

    return ProjectionView(
        year=year,
        as_of=as_of,
        jurisdiction=jurisdiction,
        income=income_view,
        set_aside=set_aside,
        quarterly_net_owing=quarterly,
        threshold=threshold,
        instalment_warning=instalment,
        ytd=ytd,
    )


async def set_declared_income(session: AsyncSession, tenant_id: UUID, year: int, amount: Decimal) -> None:
    await income_service.set_declared_income(session, tenant_id, year, amount)
