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


@pytest.mark.asyncio
async def test_aging_summary_includes_not_due_bucket():
    """Carbon redesign: unlike /reports/aging (per-client, overdue-only),
    /reports/aging/summary surfaces a not_due bucket too, since
    tenant_aging_report's _aging_bucket() excludes not-yet-due invoices
    entirely -- a real gap the new AR chart needs filled."""
    client, headers = await _tenant()
    try:
        client_id = await _client(client, headers)
        today = date.today()
        # Not yet due -- excluded from /reports/aging, must show in not_due here.
        await _issue(
            client, headers, client_id,
            invoice_date=today.isoformat(), due_date="2030-01-01", amount="500.00",
        )
        # Overdue -- must land in bucket_0_30.
        due = (today - timedelta(days=5)).isoformat()
        invoice_date = (today - timedelta(days=35)).isoformat()
        await _issue(client, headers, client_id, invoice_date=invoice_date, due_date=due, amount="300.00")

        r = await client.get("/reports/aging/summary", headers=headers)
        assert r.status_code == 200, r.text
        summary = r.json()
        # The fixture client is "taxable" (ON, 13% HST) -- amounts below
        # are the invoiced totals including tax, not the raw line amounts.
        assert summary["not_due"] == "565.00"
        assert summary["bucket_0_30"] == "339.00"
        assert summary["total_outstanding"] == "904.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_revenue_by_client_sums_billed_not_outstanding():
    """Carbon redesign: revenue-by-client sums total billed (regardless of
    payment status), distinct from the aging report's outstanding-only
    figures -- a fully paid invoice must still count here."""
    client, headers = await _tenant()
    try:
        big_client = await _client(client, headers, name="Big Client")
        small_client = await _client(client, headers, name="Small Client")

        paid_id = await _issue(
            client, headers, big_client, invoice_date="2026-05-01", due_date="2030-01-01", amount="5000.00"
        )
        await client.post(
            f"/invoices/{paid_id}/payments",
            json={"amount": "5650.00", "received_date": "2026-05-10"},
            headers=headers,
        )
        await _issue(client, headers, small_client, invoice_date="2026-05-01", due_date="2030-01-01", amount="100.00")

        r = await client.get("/reports/revenue-by-client", headers=headers)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows[0]["client_name"] == "Big Client"
        assert rows[0]["billed_cad"] == "5650.00"
        assert rows[1]["client_name"] == "Small Client"
        assert rows[1]["billed_cad"] == "113.00"
    finally:
        await client.aclose()
