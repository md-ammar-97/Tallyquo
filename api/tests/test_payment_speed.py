"""GET /reports/payment-speed -- Carbon redesign Dashboard's Payment
Collection Performance section (dashboard_design.md §12), v1 scope: an
average days-to-payment figure across fully paid invoices only. The
trend sparkline and fastest/slowest-paying-client breakdown from the
same spec section are deliberately not built here -- see
payments_service.py's average_days_to_payment docstring."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"payspeed-{uuid4()}@example.com"
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
    return client, headers


async def _issue_and_pay(
    client: httpx.AsyncClient, headers: dict, *, invoice_date: str, received_date: str, amount: str = "100.00"
) -> None:
    r = await client.post(
        "/clients",
        json={"legal_name": f"Client {uuid4()}", "country_code": "CA", "region_code": "ON", "tax_treatment": "not_registered"},
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
    r = await client.post(
        f"/invoices/{invoice_id}/payments",
        json={"amount": amount, "received_date": received_date},
        headers=headers,
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_average_days_to_payment_across_paid_invoices():
    client, headers = await _tenant()
    try:
        # Paid 10 days after issue.
        await _issue_and_pay(client, headers, invoice_date="2026-01-01", received_date="2026-01-11")
        # Paid 20 days after issue.
        await _issue_and_pay(client, headers, invoice_date="2026-02-01", received_date="2026-02-21")

        r = await client.get("/reports/payment-speed", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["invoice_count"] == 2
        assert data["average_days"] == 15.0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_average_days_to_payment_excludes_unpaid_invoices():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/clients",
            json={"legal_name": "Unpaid Client", "country_code": "CA", "region_code": "ON", "tax_treatment": "not_registered"},
            headers=headers,
        )
        client_id = r.json()["id"]
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-01-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "100.00", "amount": "100.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        assert r.status_code == 200, r.text

        r = await client.get("/reports/payment-speed", headers=headers)
        data = r.json()
        assert data["invoice_count"] == 0
        assert data["average_days"] is None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_average_days_to_payment_uses_latest_payment_for_partial_then_full():
    """A partially-paid-then-completed invoice should measure from its
    LAST payment (the one that actually completed it), not the first."""
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/clients",
            json={"legal_name": "Partial Payer", "country_code": "CA", "region_code": "ON", "tax_treatment": "not_registered"},
            headers=headers,
        )
        client_id = r.json()["id"]
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-01-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "100.00", "amount": "100.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": "40.00", "received_date": "2026-01-05"},
            headers=headers,
        )
        await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": "60.00", "received_date": "2026-01-31"},
            headers=headers,
        )

        r = await client.get("/reports/payment-speed", headers=headers)
        data = r.json()
        assert data["invoice_count"] == 1
        assert data["average_days"] == 30.0
    finally:
        await client.aclose()
