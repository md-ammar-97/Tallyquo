"""CSV exports: expenses, clients, P&L. implementation_plan.md 2.14."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"exports-{uuid4()}@example.com"
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
async def test_clients_export_csv():
    client, headers = await _tenant()
    try:
        await client.post(
            "/clients",
            json={"legal_name": "Acme", "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
            headers=headers,
        )
        r = await client.get("/clients/export.csv", headers=headers)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        lines = r.text.strip().splitlines()
        assert lines[0].startswith("legal_name,")
        assert "Acme" in lines[1]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_expenses_export_csv():
    client, headers = await _tenant()
    try:
        await client.post(
            "/expenses",
            json={"expense_date": "2026-05-01", "vendor": "Staples", "amount_total": "113.00", "tax_amount": "13.00"},
            headers=headers,
        )
        r = await client.get("/expenses/export.csv", headers=headers)
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        assert lines[0].startswith("expense_date,vendor,category,t2125_line")
        assert "Staples" in lines[1]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_pnl_income_and_expenses():
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
                "invoice_date": "2026-06-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)

        await client.post(
            "/expenses",
            json={"expense_date": "2026-06-15", "amount_total": "100.00", "tax_amount": "0"},
            headers=headers,
        )

        r = await client.get("/reports/pnl.csv", params={"group_by": "month"}, headers=headers)
        assert r.status_code == 200, r.text
        lines = r.text.strip().splitlines()
        assert lines[0] == "period,income_cad,expenses_cad,net_income_cad"
        june = next(line for line in lines[1:] if line.startswith("2026-06-01"))
        period, income, expenses, net = june.split(",")
        assert income == "1000.00"  # pre-tax subtotal -- the 13% HST is collected for the CRA, not revenue
        assert expenses == "100.00"
        assert net == "900.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_pnl_e12_rebilled_expense_excluded_from_deduction():
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
                "invoice_date": "2026-07-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Rebilled travel", "unit_rate": "200.00", "amount": "200.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)

        r = await client.post(
            "/expenses",
            json={
                "expense_date": "2026-07-01",
                "amount_total": "200.00",
                "tax_amount": "0",
                "client_id": client_id,
            },
            headers=headers,
        )
        expense_id = r.json()["id"]
        await client.post(f"/expenses/{expense_id}/rebill", params={"invoice_id": invoice_id}, headers=headers)

        r = await client.get("/reports/pnl.csv", params={"group_by": "month"}, headers=headers)
        lines = r.text.strip().splitlines()
        july = next(line for line in lines[1:] if line.startswith("2026-07-01"))
        period, income, expenses, net = july.split(",")
        assert income == "200.00"
        assert expenses == "0"  # excluded, not deducted twice against the reimbursed revenue
        assert net == "200.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_pnl_e9_meals_limited_to_50pct_deductible():
    client, headers = await _tenant()
    try:
        cats = (await client.get("/expenses/categories", headers=headers)).json()
        meals_id = next(c["id"] for c in cats if c["name"] == "Meals & entertainment")
        await client.post(
            "/expenses",
            json={"expense_date": "2026-08-01", "amount_total": "100.00", "tax_amount": "0", "category_id": meals_id},
            headers=headers,
        )
        r = await client.get("/reports/pnl.csv", params={"group_by": "month"}, headers=headers)
        lines = r.text.strip().splitlines()
        august = next(line for line in lines[1:] if line.startswith("2026-08-01"))
        assert august.split(",")[2] == "50.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_pnl_e11_capital_asset_excluded():
    client, headers = await _tenant()
    try:
        cats = (await client.get("/expenses/categories", headers=headers)).json()
        capital_id = next(c["id"] for c in cats if c["name"] == "Capital assets")
        await client.post(
            "/expenses",
            json={"expense_date": "2026-09-01", "amount_total": "2000.00", "tax_amount": "0", "category_id": capital_id},
            headers=headers,
        )
        r = await client.get("/reports/pnl.csv", params={"group_by": "month"}, headers=headers)
        lines = r.text.strip().splitlines()
        september = [line for line in lines[1:] if line.startswith("2026-09-01")]
        assert september == []  # no income and the capital expense is excluded -- no row at all
    finally:
        await client.aclose()
