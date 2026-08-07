from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from tallyquo.core.security import decode_access_token
from tallyquo.core.tenant_context import tenant_session
from tallyquo.identity import service
from tallyquo.main import app
from tallyquo.tax.snapshot_verify import run


async def _issue_one_invoice() -> tuple[str, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        email = f"snapverify-{uuid4()}@example.com"
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
            json={
                "legal_name": "Acme",
                "country_code": "CA",
                "region_code": "ON",
                "tax_treatment": "taxable",
            },
            headers=headers,
        )
        client_id = r.json()["id"]
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-06-01",
                "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        assert r.status_code == 200, r.text
        tenant_id = decode_access_token(headers["Authorization"].removeprefix("Bearer "))["tenant_id"]
        return invoice_id, tenant_id
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_snapshot_verify_finds_no_mismatch_for_a_correct_invoice():
    await _issue_one_invoice()
    mismatches = await run()
    assert mismatches == []


@pytest.mark.asyncio
async def test_snapshot_verify_detects_a_corrupted_tax_total():
    """The whole point of this job (architecture.md §9): if a stored figure
    ever drifts from what the frozen snapshot should produce, catch it."""
    invoice_id, tenant_id = await _issue_one_invoice()

    async with tenant_session(tenant_id) as session:
        await session.execute(
            text("UPDATE invoice SET tax_total = :bad WHERE id = :id"),
            {"bad": Decimal("999.99"), "id": invoice_id},
        )

    mismatches = await run()
    assert len(mismatches) == 1
    assert str(mismatches[0].invoice_id) == invoice_id
    assert mismatches[0].stored_tax_total == Decimal("999.99")
    assert mismatches[0].recomputed_tax_total == Decimal("130.00")
