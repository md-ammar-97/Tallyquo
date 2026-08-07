"""FX rate lookup: Bank of Canada's Valet API (free, public, no key).
edgecases.md C1-C8, implementation_plan.md workstreams 2.4-2.5.

Only USD is supported -- problem-statement.md Q1's own framing is "your
own template invoices a US client"; CAD is the only other currency this
product issues in, and needs no conversion.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import httpx

_SERIES = {"USD": "FXUSDCAD"}
_BASE_URL = "https://www.bankofcanada.ca/valet/observations"


@dataclass(frozen=True)
class FxRate:
    rate: Decimal
    rate_date: date  # the actual observation date -- may be earlier than
    # requested if `as_of` fell on a weekend/holiday BoC doesn't publish for.
    source: str


async def fetch_rate(currency: str, as_of: date) -> FxRate | None:
    """C2: returns None on any failure (network, unknown currency, no
    observation in range) rather than raising -- the caller must never let
    FX unavailability block issuing an invoice.

    C7: this is the only place a rate is ever looked up for a given
    (currency, date) pair -- callers convert once with the returned rate
    and never re-derive or chain a second conversion on top of it.
    """
    series = _SERIES.get(currency)
    if series is None:
        return None

    # A 7-day lookback window absorbs weekends/holidays BoC doesn't publish
    # for -- the most recent observation at or before `as_of` is used,
    # which is exactly the "last known rate" C2 asks for in the common case
    # (the source is fine, just no fresh observation for today yet).
    start = as_of - timedelta(days=7)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_BASE_URL}/{series}/json",
                params={"start_date": start.isoformat(), "end_date": as_of.isoformat()},
            )
            resp.raise_for_status()
            observations = resp.json()["observations"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None

    if not observations:
        return None

    latest = observations[-1]
    try:
        rate = Decimal(latest[series]["v"])
        rate_date = date.fromisoformat(latest["d"])
    except (KeyError, ValueError, ArithmeticError):
        return None

    return FxRate(rate=rate, rate_date=rate_date, source="boc_valet")


def convert(amount: Decimal, rate: Decimal) -> Decimal:
    """C7: convert once, to 2dp. Never chain -- callers must not feed a
    converted amount back through this a second time."""
    return (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
