"""Multi-currency. edgecases.md C1-C8, implementation_plan.md 2.4-2.5.

FX lookups are monkeypatched to avoid real network calls to Bank of
Canada in the test suite -- fx.fetch_rate's own correctness (parsing,
the weekend/holiday lookback window) isn't tested here, just that
invoices_service/payments_service use it correctly.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from tallyquo.billing import fx
from tallyquo.identity import service
from tallyquo.main import app


async def _tenant_with_client() -> tuple[httpx.AsyncClient, dict, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"currency-{uuid4()}@example.com"
    code = await service.request_otp(email, ip=None)
    r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    await client.patch(
        "/profile",
        json={
            "legal_name": "Test Co",
            "address_line1": "1 Main St",
            "city": "Toronto",
            "region_code": "ON",
            "postal_code": "M5V 1A1",
        },
        headers=headers,
    )
    await client.patch(
        "/profile/registration",
        json={
            "registration_status": "registered",
            "gst_hst_number": "123456789RT0001",
            "registration_effective_date": "2020-01-01",
        },
        headers=headers,
    )
    r = await client.post(
        "/clients",
        # US client -> zero_rated_export, so tax is 0 and the numbers
        # stay simple to reason about across these tests.
        json={"legal_name": "US Co", "country_code": "US", "tax_treatment": "zero_rated_export"},
        headers=headers,
    )
    return client, headers, r.json()["id"]


def test_convert_rounds_to_2dp_half_up():
    assert fx.convert(Decimal("100.005"), Decimal("1.35")) == Decimal("135.01")
    assert fx.convert(Decimal("10.00"), Decimal("1.333333")) == Decimal("13.33")


@pytest.mark.asyncio
async def test_c1_usd_invoice_captures_rate_and_derives_total_cad(monkeypatch):
    async def fake_fetch_rate(currency, as_of):
        assert currency == "USD"
        return fx.FxRate(rate=Decimal("1.35"), rate_date=as_of, source="boc_valet")

    monkeypatch.setattr(fx, "fetch_rate", fake_fetch_rate)

    client, headers, client_id = await _tenant_with_client()
    try:
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "currency": "USD",
                "invoice_date": "2026-06-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["currency"] == "USD"
        assert data["total"] == "1000.00"
        assert Decimal(data["fx_rate_to_cad"]) == Decimal("1.35")
        assert data["fx_rate_date"] == "2026-06-01"
        assert data["total_cad"] == "1350.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_c2_fx_source_down_never_blocks_issuing(monkeypatch):
    async def fake_fetch_rate(currency, as_of):
        return None  # source unavailable

    monkeypatch.setattr(fx, "fetch_rate", fake_fetch_rate)

    client, headers, client_id = await _tenant_with_client()
    try:
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "currency": "USD",
                "invoice_date": "2026-06-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "500.00", "amount": "500.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        assert r.status_code == 200, r.text  # never blocked
        data = r.json()
        assert data["status"] == "issued"
        assert data["fx_rate_to_cad"] is None
        assert data["total_cad"] is None
        assert data["fx_rate_source"] == "unavailable_at_issue"  # marked for review
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_c3_c4_payment_fx_gain_loss_and_per_payment_rate(monkeypatch):
    rates = {"2026-06-01": Decimal("1.30"), "2026-07-01": Decimal("1.35"), "2026-08-01": Decimal("1.25")}

    async def fake_fetch_rate(currency, as_of):
        return fx.FxRate(rate=rates[as_of.isoformat()], rate_date=as_of, source="boc_valet")

    monkeypatch.setattr(fx, "fetch_rate", fake_fetch_rate)

    client, headers, client_id = await _tenant_with_client()
    try:
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "currency": "USD",
                "invoice_date": "2026-06-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        # invoice issued at 1.30 -> total_cad = 1300.00

        # C4: two partial payments, each at its own date/rate.
        r1 = await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": "600.00", "received_date": "2026-07-01"},  # rate 1.35
            headers=headers,
        )
        assert r1.status_code == 201, r1.text
        p1 = r1.json()
        assert Decimal(p1["fx_rate_to_cad"]) == Decimal("1.35")
        assert p1["amount_cad"] == "810.00"  # 600 * 1.35
        # C3: gain/loss vs. the invoice's own frozen rate (1.30), not silently absorbed.
        assert p1["fx_gain_loss"] == "30.00"  # 810.00 - (600 * 1.30 = 780.00)

        r2 = await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": "400.00", "received_date": "2026-08-01"},  # rate 1.25
            headers=headers,
        )
        p2 = r2.json()
        assert Decimal(p2["fx_rate_to_cad"]) == Decimal("1.25")
        assert p2["amount_cad"] == "500.00"  # 400 * 1.25
        assert p2["fx_gain_loss"] == "-20.00"  # 500.00 - (400 * 1.30 = 520.00)

        detail = await client.get(f"/invoices/{invoice_id}", headers=headers)
        assert detail.json()["status"] == "paid"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_c8_credit_note_never_fetches_a_fresh_rate(monkeypatch):
    calls = []

    async def tracking_fetch_rate(currency, as_of):
        calls.append(as_of)
        return fx.FxRate(rate=Decimal("1.30"), rate_date=as_of, source="boc_valet")

    monkeypatch.setattr(fx, "fetch_rate", tracking_fetch_rate)

    client, headers, client_id = await _tenant_with_client()
    try:
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "currency": "USD",
                "invoice_date": "2026-06-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        assert calls == [date(2026, 6, 1)]  # exactly one fetch, at issue

        r2 = await client.post(
            f"/invoices/{invoice_id}/credit-note",
            json={"amount": "100.00", "reason": "partial refund"},
            headers=headers,
        )
        assert r2.status_code == 201, r2.text
        assert r2.json()["currency"] == "USD"
        assert calls == [date(2026, 6, 1)]  # still exactly one -- credit note never fetched "today"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_c6_rollup_excludes_invoice_with_no_cad_figure(monkeypatch):
    async def fake_fetch_rate(currency, as_of):
        return None  # FX unavailable -- total_cad stays NULL

    monkeypatch.setattr(fx, "fetch_rate", fake_fetch_rate)

    client, headers, client_id = await _tenant_with_client()
    try:
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "currency": "USD",
                "invoice_date": "2026-06-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)

        rollup = await client.get(f"/clients/{client_id}/rollup", headers=headers)
        june = next((p for p in rollup.json()["periods"] if p["period"] == "2026-06-01"), None)
        # Never fabricates a CAD figure from the USD total -- either the
        # period is absent, or billed_cad is 0, but never 1000.00.
        assert june is None or june["billed_cad"] == "0.00" or june["billed_cad"] == "0"
    finally:
        await client.aclose()


def test_unsupported_currency_returns_none():
    import asyncio

    result = asyncio.run(fx.fetch_rate("EUR", date(2026, 1, 1)))
    assert result is None
