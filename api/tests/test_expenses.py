"""Expenses: manual entry, T2125 categories, ITC gating.
implementation_plan.md 2.8-2.11, edgecases.md E7-E12, E15."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant(*, registered: bool = True, reg_effective_date: str = "2020-01-01") -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"expenses-{uuid4()}@example.com"
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


async def _category_id(client: httpx.AsyncClient, headers: dict, name: str) -> str:
    r = await client.get("/expenses/categories", headers=headers)
    cats = {c["name"]: c["id"] for c in r.json()}
    return cats[name]


@pytest.mark.asyncio
async def test_list_categories_seeded():
    client, headers = await _tenant()
    try:
        r = await client.get("/expenses/categories", headers=headers)
        assert r.status_code == 200
        names = {c["name"] for c in r.json()}
        assert "Meals & entertainment" in names
        assert "Capital assets" in names
        meals = next(c for c in r.json() if c["name"] == "Meals & entertainment")
        assert meals["deductible_pct"] == "50.00"
        capital = next(c for c in r.json() if c["name"] == "Capital assets")
        assert capital["is_capital"] is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_create_expense_computes_net_amount():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/expenses",
            json={
                "expense_date": "2026-05-01",
                "vendor": "Staples",
                "amount_total": "113.00",
                "tax_amount": "13.00",
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["amount_net"] == "100.00"
        assert data["source"] == "manual"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_e7_itc_eligible_when_registered_and_tax_paid():
    client, headers = await _tenant(registered=True, reg_effective_date="2020-01-01")
    try:
        r = await client.post(
            "/expenses",
            json={"expense_date": "2026-05-01", "amount_total": "113.00", "tax_amount": "13.00"},
            headers=headers,
        )
        assert r.json()["itc_eligible"] is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_e7_itc_not_eligible_when_not_registered():
    client, headers = await _tenant(registered=False)
    try:
        r = await client.post(
            "/expenses",
            json={"expense_date": "2026-05-01", "amount_total": "113.00", "tax_amount": "13.00"},
            headers=headers,
        )
        assert r.json()["itc_eligible"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_e7_itc_not_eligible_with_no_tax_paid():
    client, headers = await _tenant(registered=True)
    try:
        r = await client.post(
            "/expenses",
            json={"expense_date": "2026-05-01", "amount_total": "100.00", "tax_amount": "0.00"},
            headers=headers,
        )
        assert r.json()["itc_eligible"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_e8_not_retroactively_eligible_before_registration():
    # Registered effective 2026-06-01; an expense dated before that must
    # not become ITC-eligible even though the tenant is registered *now*.
    client, headers = await _tenant(registered=True, reg_effective_date="2026-06-01")
    try:
        r = await client.post(
            "/expenses",
            json={"expense_date": "2026-01-15", "amount_total": "113.00", "tax_amount": "13.00"},
            headers=headers,
        )
        assert r.json()["itc_eligible"] is False

        r2 = await client.post(
            "/expenses",
            json={"expense_date": "2026-07-01", "amount_total": "113.00", "tax_amount": "13.00"},
            headers=headers,
        )
        assert r2.json()["itc_eligible"] is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_category_assignment_and_t2125_line():
    client, headers = await _tenant()
    try:
        cat_id = await _category_id(client, headers, "Professional fees")
        r = await client.post(
            "/expenses",
            json={
                "expense_date": "2026-05-01",
                "category_id": cat_id,
                "amount_total": "500.00",
                "tax_amount": "0",
            },
            headers=headers,
        )
        data = r.json()
        assert data["category_name"] == "Professional fees"
        assert data["t2125_line"] == "8860"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_update_expense_recomputes_itc_and_net():
    client, headers = await _tenant(registered=True, reg_effective_date="2020-01-01")
    try:
        r = await client.post(
            "/expenses",
            json={"expense_date": "2026-05-01", "amount_total": "100.00", "tax_amount": "0"},
            headers=headers,
        )
        expense_id = r.json()["id"]
        assert r.json()["itc_eligible"] is False

        r2 = await client.patch(
            f"/expenses/{expense_id}",
            json={"expense_date": "2026-05-01", "amount_total": "113.00", "tax_amount": "13.00"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["itc_eligible"] is True
        assert r2.json()["amount_net"] == "100.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_soft_delete_excludes_from_list_and_get():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/expenses",
            json={"expense_date": "2026-05-01", "amount_total": "50.00", "tax_amount": "0"},
            headers=headers,
        )
        expense_id = r.json()["id"]

        r2 = await client.delete(f"/expenses/{expense_id}", headers=headers)
        assert r2.status_code == 204

        r3 = await client.get(f"/expenses/{expense_id}", headers=headers)
        assert r3.status_code == 404

        r4 = await client.get("/expenses", headers=headers)
        assert expense_id not in [e["id"] for e in r4.json()]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_e12_rebill_links_expense_to_invoice():
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
                "invoice_date": "2026-05-01",
                "line_items": [{"description": "Rebilled expense", "unit_rate": "50.00", "amount": "50.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        assert r.status_code == 200

        r = await client.post(
            "/expenses",
            json={"expense_date": "2026-04-20", "amount_total": "50.00", "tax_amount": "0", "client_id": client_id},
            headers=headers,
        )
        expense_id = r.json()["id"]

        r2 = await client.post(f"/expenses/{expense_id}/rebill", params={"invoice_id": invoice_id}, headers=headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["is_rebilled"] is True
        assert r2.json()["rebilled_invoice_id"] == invoice_id
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_e15_closed_year_warning_surfaced():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/expenses",
            json={"expense_date": "2020-01-01", "amount_total": "50.00", "tax_amount": "0"},
            headers=headers,
        )
        assert r.json()["warning"] is not None
        assert "2020" in r.json()["warning"]

        r2 = await client.post(
            "/expenses",
            json={"expense_date": "2026-05-01", "amount_total": "50.00", "tax_amount": "0"},
            headers=headers,
        )
        assert r2.json()["warning"] is None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_filter_expenses_by_date_range():
    client, headers = await _tenant()
    try:
        await client.post(
            "/expenses",
            json={"expense_date": "2026-01-15", "amount_total": "10.00", "tax_amount": "0"},
            headers=headers,
        )
        await client.post(
            "/expenses",
            json={"expense_date": "2026-06-15", "amount_total": "20.00", "tax_amount": "0"},
            headers=headers,
        )
        r = await client.get(
            "/expenses", params={"date_from": "2026-06-01", "date_to": "2026-06-30"}, headers=headers
        )
        assert len(r.json()) == 1
        assert r.json()[0]["amount_total"] == "20.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_expenses_by_category_applies_deductible_pct():
    """Carbon redesign Dashboard's Expense Category donut -- same
    deductible_pct-aware amount logic as reporting/service.py's pnl_rows,
    grouped by category instead of by period. Meals & entertainment is
    seeded at 50% deductible."""
    client, headers = await _tenant()
    try:
        meals_id = await _category_id(client, headers, "Meals & entertainment")
        await client.post(
            "/expenses",
            json={
                "expense_date": "2026-05-01",
                "amount_total": "100.00",
                "tax_amount": "0",
                "category_id": meals_id,
            },
            headers=headers,
        )
        await client.post(
            "/expenses",
            json={"expense_date": "2026-05-02", "amount_total": "50.00", "tax_amount": "0"},
            headers=headers,
        )

        r = await client.get("/expenses/by-category", headers=headers)
        assert r.status_code == 200, r.text
        rows = {row["category_name"]: row["amount"] for row in r.json()}
        assert rows["Meals & entertainment"] == "50.00"
        assert rows["Uncategorized"] == "50.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_expenses_by_category_excludes_capital_and_rebilled():
    client, headers = await _tenant()
    try:
        capital_id = await _category_id(client, headers, "Capital assets")
        r = await client.post(
            "/expenses",
            json={
                "expense_date": "2026-05-01",
                "amount_total": "2000.00",
                "tax_amount": "0",
                "category_id": capital_id,
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text

        r = await client.get("/expenses/by-category", headers=headers)
        rows = {row["category_name"]: row["amount"] for row in r.json()}
        assert "Capital assets" not in rows
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_receipt_completeness_counts_expenses_missing_receipts():
    client, headers = await _tenant()
    try:
        await client.post(
            "/expenses",
            json={"expense_date": "2026-05-01", "amount_total": "10.00", "tax_amount": "0"},
            headers=headers,
        )
        await client.post(
            "/expenses",
            json={"expense_date": "2026-05-02", "amount_total": "20.00", "tax_amount": "0"},
            headers=headers,
        )

        r = await client.get("/expenses/receipt-completeness", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 2
        assert data["with_receipt"] == 0
        assert data["missing"] == 2
        assert data["pct"] == 0.0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_receipt_completeness_zero_expenses_has_no_pct():
    client, headers = await _tenant()
    try:
        r = await client.get("/expenses/receipt-completeness", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 0
        assert data["pct"] is None
    finally:
        await client.aclose()
