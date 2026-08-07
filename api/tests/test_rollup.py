"""Client roll-up + aging report. implementation_plan.md workstream 2.3."""

from datetime import date, timedelta
from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"rollup-{uuid4()}@example.com"
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


async def _client(client: httpx.AsyncClient, headers: dict, *, name: str = "Acme") -> str:
    r = await client.post(
        "/clients",
        json={"legal_name": name, "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
        headers=headers,
    )
    return r.json()["id"]


async def _issue(
    client: httpx.AsyncClient,
    headers: dict,
    client_id: str,
    *,
    invoice_date: str,
    due_date: str,
    amount: str = "1000.00",
) -> str:
    r = await client.post(
        "/invoices",
        json={
            "client_id": client_id,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "line_items": [{"description": "Work", "unit_rate": amount, "amount": amount}],
        },
        headers=headers,
    )
    invoice_id = r.json()["id"]
    r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
    assert r.status_code == 200, r.text
    return invoice_id


@pytest.mark.asyncio
async def test_client_rollup_billed_collected_outstanding():
    client, headers = await _tenant()
    try:
        client_id = await _client(client, headers)
        # Both invoices dated in the same month; total is 1130.00 each
        # (1000 + 13% HST). One fully paid, one untouched.
        paid_id = await _issue(
            client, headers, client_id, invoice_date="2026-03-01", due_date="2030-01-01"
        )
        await _issue(client, headers, client_id, invoice_date="2026-03-15", due_date="2030-01-01")
        await client.post(
            f"/invoices/{paid_id}/payments",
            json={"amount": "1130.00", "received_date": "2026-03-10"},
            headers=headers,
        )

        r = await client.get(f"/clients/{client_id}/rollup", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        march = next(p for p in data["periods"] if p["period"] == "2026-03-01")
        assert march["invoice_count"] == 2
        assert march["billed_cad"] == "2260.00"
        assert march["collected_cad"] == "1130.00"
        assert march["outstanding_cad"] == "1130.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_rollup_excludes_cancelled_from_billed():
    client, headers = await _tenant()
    try:
        client_id = await _client(client, headers)
        invoice_id = await _issue(
            client, headers, client_id, invoice_date="2026-04-01", due_date="2030-01-01"
        )
        r = await client.post(f"/invoices/{invoice_id}/cancel", params={"reason": "test"}, headers=headers)
        assert r.status_code == 204

        r = await client.get(f"/clients/{client_id}/rollup", headers=headers)
        periods = r.json()["periods"]
        april = next((p for p in periods if p["period"] == "2026-04-01"), None)
        assert april is None or april["invoice_count"] == 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_aging_buckets():
    client, headers = await _tenant()
    try:
        client_id = await _client(client, headers)
        today = date.today()

        async def _overdue_by(days: int) -> None:
            due = today - timedelta(days=days)
            invoice_date = due - timedelta(days=30)
            await _issue(
                client,
                headers,
                client_id,
                invoice_date=invoice_date.isoformat(),
                due_date=due.isoformat(),
            )

        await _overdue_by(10)   # bucket_0_30
        await _overdue_by(45)   # bucket_31_60
        await _overdue_by(75)   # bucket_61_90
        await _overdue_by(120)  # bucket_90_plus

        r = await client.get(f"/clients/{client_id}/rollup", headers=headers)
        aging = r.json()["aging"]
        assert aging["bucket_0_30"] == "1130.00"
        assert aging["bucket_31_60"] == "1130.00"
        assert aging["bucket_61_90"] == "1130.00"
        assert aging["bucket_90_plus"] == "1130.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_aging_report_tenant_wide_sorted_by_outstanding():
    client, headers = await _tenant()
    try:
        big_client = await _client(client, headers, name="Big Debtor")
        small_client = await _client(client, headers, name="Small Debtor")
        today = date.today()
        due = (today - timedelta(days=10)).isoformat()
        past = (today - timedelta(days=40)).isoformat()

        await _issue(client, headers, big_client, invoice_date=past, due_date=due, amount="5000.00")
        await _issue(client, headers, small_client, invoice_date=past, due_date=due, amount="100.00")

        r = await client.get("/reports/aging", headers=headers)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows[0]["client_name"] == "Big Debtor"
        assert rows[0]["total_outstanding"] == "5650.00"
        assert rows[1]["client_name"] == "Small Debtor"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rollup_404_for_nonexistent_client():
    client, headers = await _tenant()
    try:
        r = await client.get(f"/clients/{uuid4()}/rollup", headers=headers)
        assert r.status_code == 404
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_not_yet_due_invoice_excluded_from_aging():
    client, headers = await _tenant()
    try:
        client_id = await _client(client, headers)
        await _issue(client, headers, client_id, invoice_date="2026-03-01", due_date="2030-01-01")

        r = await client.get(f"/clients/{client_id}/rollup", headers=headers)
        aging = r.json()["aging"]
        assert aging["bucket_0_30"] == "0.00" or aging["bucket_0_30"] == "0"
        assert all(v in ("0", "0.00") for v in aging.values())
    finally:
        await client.aclose()
