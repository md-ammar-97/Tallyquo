from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant_with_issued_invoice(
    *, due_date: str | None = None, invoice_date: str = "2026-01-01"
) -> tuple[httpx.AsyncClient, dict, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"payments-{uuid4()}@example.com"
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
        json={"legal_name": "Acme", "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
        headers=headers,
    )
    client_id = r.json()["id"]
    body = {
        "client_id": client_id,
        "invoice_date": invoice_date,
        "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
    }
    if due_date:
        body["due_date"] = due_date
    r = await client.post("/invoices", json=body, headers=headers)
    invoice_id = r.json()["id"]
    r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
    assert r.status_code == 200, r.text
    return client, headers, invoice_id


@pytest.mark.asyncio
async def test_full_payment_marks_invoice_paid():
    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        r = await client.get(f"/invoices/{invoice_id}", headers=headers)
        total = r.json()["total"]  # "1130.00"

        r = await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": total, "received_date": "2026-01-15"},
            headers=headers,
        )
        assert r.status_code == 201, r.text

        r = await client.get(f"/invoices/{invoice_id}", headers=headers)
        assert r.json()["status"] == "paid"
        assert r.json()["amount_paid"] == total
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_partial_payment_marks_partially_paid():
    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        r = await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": "500.00", "received_date": "2026-01-15"},
            headers=headers,
        )
        assert r.status_code == 201

        r = await client.get(f"/invoices/{invoice_id}", headers=headers)
        assert r.json()["status"] == "partially_paid"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_l10_overpayment_blocked():
    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        r = await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": "5000.00", "received_date": "2026-01-15"},
            headers=headers,
        )
        assert r.status_code == 422
        assert "overpay" in r.json()["detail"].lower()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_l11_payment_blocked_on_cancelled_invoice():
    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        r = await client.post(f"/invoices/{invoice_id}/cancel", params={"reason": "test"}, headers=headers)
        assert r.status_code == 204

        r = await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": "100.00", "received_date": "2026-01-15"},
            headers=headers,
        )
        assert r.status_code == 422
        assert "cancelled" in r.json()["detail"].lower()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_l12_reversal_recalculates_status():
    # Due date must be in the future, or the post-reversal status would
    # correctly resolve to "overdue" rather than "issued" -- not a bug,
    # just a fact this test needs to control for.
    client, headers, invoice_id = await _tenant_with_issued_invoice(due_date="2027-01-01")
    try:
        r = await client.get(f"/invoices/{invoice_id}", headers=headers)
        total = r.json()["total"]

        r = await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": total, "received_date": "2026-01-15"},
            headers=headers,
        )
        payment_id = r.json()["id"]

        r = await client.get(f"/invoices/{invoice_id}", headers=headers)
        assert r.json()["status"] == "paid"

        r = await client.delete(
            f"/invoices/payments/{payment_id}", params={"reason": "duplicate entry"}, headers=headers
        )
        assert r.status_code == 204

        r = await client.get(f"/invoices/{invoice_id}", headers=headers)
        assert r.json()["status"] == "issued"
        assert r.json()["amount_paid"] == "0.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_overdue_status_derived_from_due_date():
    client, headers, invoice_id = await _tenant_with_issued_invoice(
        invoice_date="2020-01-01", due_date="2020-01-15"
    )
    try:
        r = await client.get(f"/invoices/{invoice_id}", headers=headers)
        assert r.json()["status"] == "overdue"
    finally:
        await client.aclose()
