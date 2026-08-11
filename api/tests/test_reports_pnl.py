"""GET /reports/pnl -- Carbon redesign Dashboard's 12-month Revenue/
Expenses/Net-Income chart and Monthly Expense Trend (dashboard_design.md
§4, §16). A thin JSON wrapper around reporting/service.py's pnl_rows(),
already exhaustively covered as CSV via test_reporting.py-equivalent
CSV export tests -- this file covers the new JSON surface and its
group_by validation specifically."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"pnl-{uuid4()}@example.com"
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
    return client, headers


@pytest.mark.asyncio
async def test_pnl_json_matches_csv_totals_for_same_period():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/clients",
            json={"legal_name": "Acme", "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
            headers=headers,
        )
        client_id = r.json()["id"]
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-03-05",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        assert r.status_code == 200, r.text

        r = await client.get("/reports/pnl?group_by=month", headers=headers)
        assert r.status_code == 200, r.text
        rows = r.json()
        march = next(row for row in rows if row["period"] == "2026-03-01")
        assert march["income"] == "1000.00"
        assert march["net_income"] == "1000.00"

        r_csv = await client.get("/reports/pnl.csv?group_by=month", headers=headers)
        assert r_csv.status_code == 200
        assert "2026-03-01,1000.00" in r_csv.text
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_pnl_json_rejects_invalid_group_by():
    client, headers = await _tenant()
    try:
        r = await client.get("/reports/pnl?group_by=fortnight", headers=headers)
        assert r.status_code == 422
    finally:
        await client.aclose()
