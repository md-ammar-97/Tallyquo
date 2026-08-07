from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _authed_client() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"clients-{uuid4()}@example.com"
    code = await service.request_otp(email, ip=None)
    r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
    tokens = r.json()
    return client, {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.mark.asyncio
async def test_create_client_and_list():
    client, headers = await _authed_client()
    try:
        body = {
            "legal_name": "Acme Ltd.",
            "country_code": "CA",
            "region_code": "ON",
            "tax_treatment": "taxable",
        }
        r = await client.post("/clients", json=body, headers=headers)
        assert r.status_code == 201, r.text
        client_id = r.json()["id"]

        r = await client.get("/clients", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["legal_name"] == "Acme Ltd."

        r = await client.get(f"/clients/{client_id}", headers=headers)
        assert r.status_code == 200
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_taxable_requires_region_edgecase_d7():
    """edgecases.md D7: taxable clients must have a region; others don't need one."""
    client, headers = await _authed_client()
    try:
        body = {
            "legal_name": "No Region Inc.",
            "country_code": "CA",
            "tax_treatment": "taxable",
        }
        r = await client.post("/clients", json=body, headers=headers)
        assert r.status_code == 422

        body["tax_treatment"] = "zero_rated_export"
        body["country_code"] = "US"
        r = await client.post("/clients", json=body, headers=headers)
        assert r.status_code == 201
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_two_tenants_do_not_see_each_others_clients():
    client_a, headers_a = await _authed_client()
    client_b, headers_b = await _authed_client()
    try:
        await client_a.post(
            "/clients",
            json={
                "legal_name": "Tenant A Client",
                "country_code": "CA",
                "region_code": "BC",
                "tax_treatment": "taxable",
            },
            headers=headers_a,
        )
        r = await client_b.get("/clients", headers=headers_b)
        assert r.json() == []
    finally:
        await client_a.aclose()
        await client_b.aclose()


@pytest.mark.asyncio
async def test_evidence_upload_and_list():
    client, headers = await _authed_client()
    try:
        r = await client.post(
            "/clients",
            json={
                "legal_name": "US Client",
                "country_code": "US",
                "tax_treatment": "zero_rated_export",
            },
            headers=headers,
        )
        client_id = r.json()["id"]

        r = await client.post(
            f"/clients/{client_id}/evidence",
            json={
                "kind": "non_residency_attestation",
                "file_ref": "tenant/evidence/abc.pdf",
                "file_hash": "deadbeef",
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text

        r = await client.get(f"/clients/{client_id}/evidence", headers=headers)
        assert len(r.json()) == 1
        assert r.json()[0]["kind"] == "non_residency_attestation"
    finally:
        await client.aclose()
