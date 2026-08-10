from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.auth import CurrentUser, get_current_user, get_db
from tallyquo.projection import service
from tallyquo.projection.engine import MarginalTaxResult
from tallyquo.projection.schemas import (
    CppOut,
    DeclaredIncomeIn,
    DerivedIncomeOut,
    IncomeViewOut,
    InstalmentWarningOut,
    MarginalTaxOut,
    ProjectionOut,
    QuarterNetOwingOut,
    SetAsideOut,
    TaxBandOut,
    ThresholdOut,
    YtdActualsOut,
)

router = APIRouter(prefix="/projection", tags=["projection"])


def _marginal_tax_out(result: MarginalTaxResult) -> MarginalTaxOut:
    return MarginalTaxOut(
        jurisdiction=result.jurisdiction,
        net_income=result.net_income,
        bands=[
            TaxBandOut(
                income_from=b.income_from,
                income_to=b.income_to,
                rate=b.rate,
                taxable_amount=b.taxable_amount,
                tax=b.tax,
            )
            for b in result.bands
        ],
        total_tax=result.total_tax,
    )


def _to_out(view: service.ProjectionView) -> ProjectionOut:
    set_aside = view.set_aside
    return ProjectionOut(
        year=view.year,
        as_of=view.as_of.isoformat(),
        jurisdiction=view.jurisdiction,
        income=IncomeViewOut(
            mode=view.income.mode,
            derived=DerivedIncomeOut(
                extrapolated_annual_income=view.income.derived.extrapolated_annual_income,
                scheduled_recurring_income=view.income.derived.scheduled_recurring_income,
                projected_annual_income=view.income.derived.projected_annual_income,
                is_low_confidence=view.income.derived.is_low_confidence,
                method=view.income.derived.method,
            ),
            declared_annual_income=view.income.declared_annual_income,
            active_projected_income=view.income.active_projected_income,
            variance_from_derived=view.income.variance_from_derived,
        ),
        set_aside=SetAsideOut(
            net_business_income=set_aside.net_business_income,
            federal_tax=_marginal_tax_out(set_aside.federal_tax),
            provincial_tax=_marginal_tax_out(set_aside.provincial_tax),
            cpp=CppOut(
                pensionable_earnings=set_aside.cpp.pensionable_earnings,
                base_contribution=set_aside.cpp.base_contribution,
                cpp2_pensionable_earnings=set_aside.cpp.cpp2_pensionable_earnings,
                cpp2_contribution=set_aside.cpp.cpp2_contribution,
                total_contribution=set_aside.cpp.total_contribution,
            ),
            total_estimated_tax_and_cpp=set_aside.total_estimated_tax_and_cpp,
            recommended_set_aside_pct=set_aside.recommended_set_aside_pct,
        ),
        quarterly_net_owing=[
            QuarterNetOwingOut(
                period=str(q.period),
                collected=q.collected,
                itcs_claimable=q.itcs_claimable,
                net_owing=q.net_owing,
            )
            for q in view.quarterly_net_owing
        ],
        threshold=ThresholdOut(
            rolling_revenue=view.threshold.rolling_revenue,
            threshold=view.threshold.threshold,
            pct_of_threshold=view.threshold.pct_of_threshold,
            window_start=view.threshold.window_start.isoformat(),
            window_end=view.threshold.window_end.isoformat(),
            escalation=view.threshold.escalation,
        ),
        instalment_warning=InstalmentWarningOut(
            applies=view.instalment_warning.applies,
            projected_net_tax_owing=view.instalment_warning.projected_net_tax_owing,
            threshold=view.instalment_warning.threshold,
        ),
        ytd=YtdActualsOut(
            income=view.ytd.income,
            expenses=view.ytd.expenses,
            net_income=view.ytd.net_income,
        ),
    )


@router.get("", response_model=ProjectionOut)
async def get_projection(
    year: int | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectionOut:
    try:
        view = await service.build_projection(db, current_user.tenant_id, year=year)
    except service.NoBusinessProfile as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except service.JurisdictionNotSupported as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return _to_out(view)


@router.put("/declared-income", status_code=204)
async def put_declared_income(
    body: DeclaredIncomeIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.set_declared_income(db, current_user.tenant_id, body.year, body.declared_annual_income)


@router.delete("/declared-income/{year}", status_code=204)
async def delete_declared_income(
    year: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await db.execute(text("DELETE FROM income_declaration WHERE year = :year"), {"year": year})
