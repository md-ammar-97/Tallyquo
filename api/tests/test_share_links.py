"""Public shareable invoice links. implementation_plan.md 2.12-2.13
(reframed: no email, a durable revocable public link instead)."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant_with_invoice(*, issue: bool = True) -> tuple[httpx.AsyncClient, dict, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"share-{uuid4()}@example.com"
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
    r = await client.post(
        "/invoices",
        json={
            "client_id": client_id,
            "invoice_date": "2026-05-01",
            "due_date": "2030-01-01",
            "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
        },
        headers=headers,
    )
    invoice_id = r.json()["id"]
    if issue:
        r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        assert r.status_code == 200, r.text
    return client, headers, invoice_id


@pytest.mark.asyncio
async def test_create_share_link_and_view_publicly():
    client, headers, invoice_id = await _tenant_with_invoice()
    try:
        r = await client.post(f"/invoices/{invoice_id}/share", headers=headers)
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        assert len(token) > 20

        # No Authorization header at all -- genuinely public.
        r2 = await client.get(f"/public/invoices/{token}")
        assert r2.status_code == 200, r2.text
        assert r2.json()["id"] == invoice_id
        assert r2.json()["line_items"][0]["description"] == "Work"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_share_link_is_stable_across_calls():
    client, headers, invoice_id = await _tenant_with_invoice()
    try:
        r1 = await client.post(f"/invoices/{invoice_id}/share", headers=headers)
        r2 = await client.post(f"/invoices/{invoice_id}/share", headers=headers)
        assert r1.json()["token"] == r2.json()["token"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_public_pdf_download():
    client, headers, invoice_id = await _tenant_with_invoice()
    try:
        r = await client.post(f"/invoices/{invoice_id}/share", headers=headers)
        token = r.json()["token"]

        r2 = await client.get(f"/public/invoices/{token}/pdf")
        assert r2.status_code == 200
        assert r2.headers["content-type"] == "application/pdf"
        assert r2.content[:4] == b"%PDF"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_draft_invoice_cannot_be_shared():
    client, headers, invoice_id = await _tenant_with_invoice(issue=False)
    try:
        r = await client.post(f"/invoices/{invoice_id}/share", headers=headers)
        assert r.status_code == 409
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_revoke_share_link_invalidates_it():
    client, headers, invoice_id = await _tenant_with_invoice()
    try:
        r = await client.post(f"/invoices/{invoice_id}/share", headers=headers)
        token = r.json()["token"]

        r2 = await client.delete(f"/invoices/{invoice_id}/share", headers=headers)
        assert r2.status_code == 204

        r3 = await client.get(f"/public/invoices/{token}")
        assert r3.status_code == 404

        # Revoking twice is a clean 404, not a crash.
        r4 = await client.delete(f"/invoices/{invoice_id}/share", headers=headers)
        assert r4.status_code == 404
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_regenerating_after_revoke_issues_a_new_token():
    client, headers, invoice_id = await _tenant_with_invoice()
    try:
        r1 = await client.post(f"/invoices/{invoice_id}/share", headers=headers)
        token1 = r1.json()["token"]
        await client.delete(f"/invoices/{invoice_id}/share", headers=headers)

        r2 = await client.post(f"/invoices/{invoice_id}/share", headers=headers)
        token2 = r2.json()["token"]
        assert token1 != token2

        r3 = await client.get(f"/public/invoices/{token1}")
        assert r3.status_code == 404  # old token stays dead
        r4 = await client.get(f"/public/invoices/{token2}")
        assert r4.status_code == 200
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_bogus_token_returns_404_not_error():
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        r = await client.get("/public/invoices/not-a-real-token")
        assert r.status_code == 404
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_share_link_does_not_leak_across_tenants():
    client1, headers1, invoice_id1 = await _tenant_with_invoice()
    client2, headers2, invoice_id2 = await _tenant_with_invoice()
    try:
        r1 = await client1.post(f"/invoices/{invoice_id1}/share", headers=headers1)
        token1 = r1.json()["token"]

        # Tenant 2's own auth can't be used to revoke tenant 1's link via
        # tenant 1's invoice id -- RLS scopes the invoice lookup itself.
        r = await client2.delete(f"/invoices/{invoice_id1}/share", headers=headers2)
        assert r.status_code == 404

        # And the public link still resolves correctly to tenant 1's data.
        r2 = await client1.get(f"/public/invoices/{token1}")
        assert r2.json()["id"] == invoice_id1
    finally:
        await client1.aclose()
        await client2.aclose()
