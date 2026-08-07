from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, model_validator

CADENCES = {"weekly", "biweekly", "monthly", "quarterly", "semiannual", "annual"}


class RecurringRuleIn(BaseModel):
    client_id: UUID
    source_invoice_id: UUID
    cadence: str
    day_of_period: int | None = None
    next_run_date: date
    end_date: date | None = None
    occurrences_remaining: int | None = None
    auto_issue: bool = False

    @model_validator(mode="after")
    def validate_cadence(self) -> "RecurringRuleIn":
        if self.cadence not in CADENCES:
            raise ValueError(f"cadence must be one of {sorted(CADENCES)}")
        if self.day_of_period is not None and not (1 <= self.day_of_period <= 31):
            raise ValueError("day_of_period must be between 1 and 31")
        return self


class RecurringRuleOut(BaseModel):
    id: UUID
    client_id: UUID
    client_name: str | None = None
    source_invoice_id: UUID | None
    cadence: str
    day_of_period: int | None
    next_run_date: date
    end_date: date | None
    occurrences_remaining: int | None
    auto_issue: bool
    is_paused: bool
    last_run_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecurringRulePatch(BaseModel):
    cadence: str | None = None
    day_of_period: int | None = None
    end_date: date | None = None
    occurrences_remaining: int | None = None
    auto_issue: bool | None = None
