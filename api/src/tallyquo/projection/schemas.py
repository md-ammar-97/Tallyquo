from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DeclaredIncomeIn(BaseModel):
    year: int
    declared_annual_income: Decimal


class TaxBandOut(BaseModel):
    income_from: Decimal
    income_to: Decimal | None
    rate: Decimal
    taxable_amount: Decimal
    tax: Decimal


class MarginalTaxOut(BaseModel):
    jurisdiction: str
    net_income: Decimal
    bands: list[TaxBandOut]
    total_tax: Decimal


class CppOut(BaseModel):
    pensionable_earnings: Decimal
    base_contribution: Decimal
    cpp2_pensionable_earnings: Decimal
    cpp2_contribution: Decimal
    total_contribution: Decimal


class SetAsideOut(BaseModel):
    net_business_income: Decimal
    federal_tax: MarginalTaxOut
    provincial_tax: MarginalTaxOut
    cpp: CppOut
    total_estimated_tax_and_cpp: Decimal
    recommended_set_aside_pct: Decimal


class DerivedIncomeOut(BaseModel):
    extrapolated_annual_income: Decimal
    scheduled_recurring_income: Decimal
    projected_annual_income: Decimal
    is_low_confidence: bool
    method: str


class IncomeViewOut(BaseModel):
    mode: str
    derived: DerivedIncomeOut
    declared_annual_income: Decimal | None
    active_projected_income: Decimal
    variance_from_derived: Decimal | None


class QuarterNetOwingOut(BaseModel):
    period: str
    collected: Decimal
    itcs_claimable: Decimal
    net_owing: Decimal


class ThresholdOut(BaseModel):
    rolling_revenue: Decimal
    threshold: Decimal
    pct_of_threshold: Decimal
    window_start: str
    window_end: str
    escalation: str


class InstalmentWarningOut(BaseModel):
    applies: bool
    projected_net_tax_owing: Decimal
    threshold: Decimal


class YtdActualsOut(BaseModel):
    income: Decimal
    expenses: Decimal
    net_income: Decimal


class ProjectionOut(BaseModel):
    year: int
    as_of: str
    jurisdiction: str
    income: IncomeViewOut
    set_aside: SetAsideOut
    quarterly_net_owing: list[QuarterNetOwingOut]
    threshold: ThresholdOut
    instalment_warning: InstalmentWarningOut
    ytd: YtdActualsOut


class RecurringForecastRowOut(BaseModel):
    period: date
    amount: Decimal


class TaxReserveIn(BaseModel):
    year: int
    reserved_amount: Decimal


class TaxReserveOut(BaseModel):
    year: int
    reserved_amount: Decimal | None
