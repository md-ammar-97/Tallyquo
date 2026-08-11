from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class PnlRowOut(BaseModel):
    period: date
    income: Decimal
    expenses: Decimal
    net_income: Decimal
