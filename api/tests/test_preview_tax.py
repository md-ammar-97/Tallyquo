"""End-to-end: DB-seeded rates + real business_profile/client rows through
the /invoices/preview-tax endpoint -- proves tax/loader.py and
tax/context_builder.py wire correctly to the pure engine, on top of the
already-exhaustive pure-function suite in test_tax_engine.py."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _registered_tenant_client(*, region: str, country: str = "CA") -> tuple[httpx.AsyncClient, dict, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"previewtax-{uuid4()}@example.com"
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
            "legal_name": "Test Client",
            "country_code": country,
            "region_code": region if country == "CA" else None,
            "tax_treatment": "taxable" if country == "CA" else "zero_rated_export",
        },
        headers=headers,
    )
    client_id = r.json()["id"]
    return client, headers, client_id


@pytest.mark.asyncio
async def test_preview_tax_ontario_13_percent_hst():
    client, headers, client_id = await _registered_tenant_client(region="ON")
    try:
        r = await client.post(
            "/invoices/preview-tax",
            json={
                "client_id": client_id,
                "invoice_date": "2026-06-01",
                "line_items": [{"amount": "1000.00", "is_taxable": True}],
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["treatment"] == "taxable"
        assert data["jurisdiction"] == "CA-ON"
        assert data["lines"][0]["tax_type"] == "hst"
        assert data["lines"][0]["amount"] == "130.00"
        assert data["total"] == "1130.00"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_preview_tax_nova_scotia_rate_change_from_real_seed_data():
    """edgecases.md X2/X3 against the actual seeded DB rows, not a
    hand-built test fixture -- proves the real migration data is correct."""
    client, headers, client_id = await _registered_tenant_client(region="NS")
    try:
        r_before = await client.post(
            "/invoices/preview-tax",
            json={
                "client_id": client_id,
                "invoice_date": "2025-03-15",
                "line_items": [{"amount": "1000.00"}],
            },
            headers=headers,
        )
        r_after = await client.post(
            "/invoices/preview-tax",
            json={
                "client_id": client_id,
                "invoice_date": "2025-04-15",
                "line_items": [{"amount": "1000.00"}],
            },
            headers=headers,
        )
        assert r_before.json()["lines"][0]["rate"] == "0.15000"
        assert r_after.json()["lines"][0]["rate"] == "0.14000"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_preview_tax_us_client_zero_rated():
    client, headers, client_id = await _registered_tenant_client(region="", country="US")
    try:
        r = await client.post(
            "/invoices/preview-tax",
            json={
                "client_id": client_id,
                "invoice_date": "2026-06-01",
                "line_items": [{"amount": "1000.00"}],
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["treatment"] == "zero_rated_export"
        assert data["tax_total"] == "0.00"
        assert any("evidence" in w.lower() for w in data["warnings"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_preview_tax_missing_profile_is_a_clean_422():
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"noprofile-{uuid4()}@example.com"
    code = await service.request_otp(email, ip=None)
    r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    try:
        r = await client.post(
            "/invoices/preview-tax",
            json={
                "client_id": str(uuid4()),
                "invoice_date": "2026-06-01",
                "line_items": [{"amount": "100.00"}],
            },
            headers=headers,
        )
        assert r.status_code == 422
    finally:
        await client.aclose()
