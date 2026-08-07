from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _authed_client() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"profile-{uuid4()}@example.com"
    code = await service.request_otp(email, ip=None)
    r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
    tokens = r.json()
    return client, {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.mark.asyncio
async def test_profile_starts_empty_then_upserts():
    client, headers = await _authed_client()
    try:
        r = await client.get("/profile", headers=headers)
        assert r.status_code == 200
        assert r.json() is None

        body = {
            "legal_name": "Jane Doe",
            "address_line1": "123 Main St",
            "city": "Toronto",
            "region_code": "ON",
            "postal_code": "M5V 1A1",
        }
        r = await client.patch("/profile", json=body, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["legal_name"] == "Jane Doe"
        assert data["registration_status"] == "not_registered"

        r = await client.get("/profile", headers=headers)
        assert r.json()["legal_name"] == "Jane Doe"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_registration_requires_bn_when_registered():
    client, headers = await _authed_client()
    try:
        await client.patch(
            "/profile",
            json={
                "legal_name": "Jane Doe",
                "address_line1": "123 Main St",
                "city": "Toronto",
                "region_code": "ON",
                "postal_code": "M5V 1A1",
            },
            headers=headers,
        )
        r = await client.patch(
            "/profile/registration",
            json={"registration_status": "registered"},
            headers=headers,
        )
        assert r.status_code == 422

        r = await client.patch(
            "/profile/registration",
            json={
                "registration_status": "registered",
                "gst_hst_number": "123456789RT0001",
                "registration_effective_date": "2026-01-01",
            },
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["registration_status"] == "registered"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_payment_instruction_never_returns_full_fields_unless_revealed():
    client, headers = await _authed_client()
    try:
        r = await client.post(
            "/payment-instructions",
            json={
                "label": "Main EFT",
                "method": "eft",
                "currency": "CAD",
                "fields": {"account_number": "1234567890"},
            },
            headers=headers,
        )
        assert r.status_code == 201
        instruction_id = r.json()["id"]
        assert r.json()["fields_masked"]["account_number"] == "****7890"

        r = await client.get("/payment-instructions", headers=headers)
        assert r.json()[0]["fields_masked"]["account_number"] == "****7890"
        assert "1234567890" not in r.text

        r = await client.get(f"/payment-instructions/{instruction_id}/reveal", headers=headers)
        assert r.json()["fields"]["account_number"] == "1234567890"
    finally:
        await client.aclose()
