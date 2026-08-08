"""Integration coverage for the projection module's DB-facing pieces:
income_service, gst_service, and the /projection HTTP surface. The
pure-calculation cases (marginal tax, CPP) are covered exhaustively in
test_projection_engine.py without a DB -- this file is about whether
those engines get fed the right numbers from real data."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant(*, registered: bool = True, reg_effective_date: str = "2020-01-01") -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"projection-{uuid4()}@example.com"
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
    if registered:
        await client.patch(
            "/profile/registration",
            json={
                "registration_status": "registered",
                "gst_hst_number": "123456789RT0001",
                "registration_effective_date": reg_effective_date,
            },
            headers=headers,
        )
    return client, headers


async def _issue_invoice(client: httpx.AsyncClient, headers: dict, *, amount: str, invoice_date: str) -> str:
    r = await client.post(
        "/clients",
        json={"legal_name": f"Client {uuid4()}", "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
        headers=headers,
    )
    client_id = r.json()["id"]
    r = await client.post(
        "/invoices",
        json={
            "client_id": client_id,
            "invoice_date": invoice_date,
            "due_date": "2030-01-01",
            "line_items": [{"description": "Work", "unit_rate": amount, "amount": amount}],
        },
        headers=headers,
    )
    invoice_id = r.json()["id"]
    r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
    assert r.status_code == 200, r.text
    return invoice_id


@pytest.mark.asyncio
async def test_projection_requires_business_profile():
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        email = f"projection-noprofile-{uuid4()}@example.com"
        code = await service.request_otp(email, ip=None)
        r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await client.get("/projection", headers=headers)
        assert r.status_code == 422
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_projection_reflects_issued_invoice_income():
    client, headers = await _tenant()
    try:
        await _issue_invoice(client, headers, amount="10000.00", invoice_date="2026-01-15")
        r = await client.get("/projection?year=2026", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["jurisdiction"] == "ON"
        assert data["income"]["mode"] == "derived"
        # $10,000 collected via HST (13%) = $1,300 -- shows up in Q1.
        q1 = next(q for q in data["quarterly_net_owing"] if q["period"] == "2026-Q1")
        assert q1["collected"] == "1300.00"
        # threshold: $10,000 counts toward the rolling $30,000 window.
        assert data["threshold"]["rolling_revenue"] == "10000.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_declared_income_overrides_derived_and_shows_variance():
    client, headers = await _tenant()
    try:
        await _issue_invoice(client, headers, amount="5000.00", invoice_date="2026-01-10")
        r = await client.put(
            "/projection/declared-income",
            json={"year": 2026, "declared_annual_income": "120000.00"},
            headers=headers,
        )
        assert r.status_code == 204, r.text

        r = await client.get("/projection?year=2026", headers=headers)
        data = r.json()
        assert data["income"]["mode"] == "declared"
        assert data["income"]["declared_annual_income"] == "120000.00"
        assert data["income"]["active_projected_income"] == "120000.00"
        assert data["income"]["variance_from_derived"] is not None

        r = await client.delete("/projection/declared-income/2026", headers=headers)
        assert r.status_code == 204
        r = await client.get("/projection?year=2026", headers=headers)
        assert r.json()["income"]["mode"] == "derived"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_o5_expense_itc_reduces_net_owing_even_without_tax_type():
    """Regression for a real bug caught while building this: itc_eligible
    is the GST/HST-ITC signal, tax_type on expense is optional and often
    blank -- the net-owing query must not silently drop untyped ITCs."""
    client, headers = await _tenant()
    try:
        await _issue_invoice(client, headers, amount="1000.00", invoice_date="2026-02-01")
        r = await client.post(
            "/expenses",
            json={"expense_date": "2026-02-05", "amount_total": "113.00", "tax_amount": "13.00"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["itc_eligible"] is True
        assert r.json()["tax_type"] is None

        r = await client.get("/projection?year=2026", headers=headers)
        q1 = next(q for q in r.json()["quarterly_net_owing"] if q["period"] == "2026-Q1")
        assert q1["itcs_claimable"] == "13.00"
        # $1000 * 13% HST = $130 collected, minus $13 ITC = $117 net owing.
        assert q1["net_owing"] == "117.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_threshold_counts_not_registered_revenue():
    """S1's underlying mechanism: revenue earned BEFORE registering still
    has to count, or the threshold could never trigger a first registration."""
    client, headers = await _tenant(registered=False)
    try:
        await _issue_invoice(client, headers, amount="25000.00", invoice_date="2026-03-01")
        r = await client.get("/projection?year=2026", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["threshold"]["rolling_revenue"] == "25000.00"
        assert r.json()["threshold"]["escalation"] == "attention"  # 83.3% of $30k
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_instalment_warning_excludes_gst_net_owing():
    """GST/HST net-owing and the income-tax instalment threshold are two
    separate CRA mechanisms -- a large GST collection shouldn't trip the
    income-tax instalment warning on its own, and the warning's own
    figure should equal the set-aside total, not a blend of the two."""
    client, headers = await _tenant()
    try:
        # $50,000 income -> real income tax + CPP, but nowhere near the
        # $3,000 instalment threshold at this income level; the HST
        # collected on top ($6,500) must not be what tips it over.
        await _issue_invoice(client, headers, amount="50000.00", invoice_date="2026-01-15")
        r = await client.get("/projection?year=2026", headers=headers)
        data = r.json()
        assert data["instalment_warning"]["projected_net_tax_owing"] == data["set_aside"]["total_estimated_tax_and_cpp"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_s7_credit_note_nets_out_of_threshold():
    """edgecases.md S7: a credited invoice shouldn't keep counting its
    full original amount toward the small-supplier threshold."""
    client, headers = await _tenant()
    try:
        invoice_id = await _issue_invoice(client, headers, amount="25000.00", invoice_date="2026-03-01")
        r = await client.get("/projection?year=2026", headers=headers)
        assert r.json()["threshold"]["rolling_revenue"] == "25000.00"

        r = await client.post(
            f"/invoices/{invoice_id}/credit-note",
            json={"amount": "10000.00", "tax_amount": "1300.00", "reason": "Scope reduced"},
            headers=headers,
        )
        assert r.status_code == 201, r.text

        r = await client.get("/projection?year=2026", headers=headers)
        assert r.json()["threshold"]["rolling_revenue"] == "15000.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_set_aside_never_negative_on_a_loss_year():
    """P4: expenses exceeding revenue -- set-aside should be $0, not crash
    or go negative."""
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/expenses",
            json={"expense_date": "2026-01-05", "amount_total": "5000.00", "tax_amount": "0.00"},
            headers=headers,
        )
        assert r.status_code == 201, r.text

        r = await client.get("/projection?year=2026", headers=headers)
        data = r.json()
        assert float(data["set_aside"]["net_business_income"]) == 0.0
        assert data["set_aside"]["recommended_set_aside_pct"] == "0.00"
    finally:
        await client.aclose()
