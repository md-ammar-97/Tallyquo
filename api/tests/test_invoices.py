"""Invoice drafts + the issuance transaction. edgecases.md §3 (numbering)
and §7 (lifecycle/immutability)."""

import asyncio
from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant_with_client(*, region: str = "ON") -> tuple[httpx.AsyncClient, dict, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"invoices-{uuid4()}@example.com"
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
            "legal_name": "Acme Ltd.",
            "country_code": "CA",
            "region_code": region,
            "tax_treatment": "taxable",
        },
        headers=headers,
    )
    client_id = r.json()["id"]
    return client, headers, client_id


async def _draft(client: httpx.AsyncClient, headers: dict, client_id: str, **overrides) -> dict:
    body = {
        "client_id": client_id,
        "invoice_date": "2026-06-01",
        "line_items": [{"description": "Consulting", "unit_rate": "1000.00", "amount": "1000.00"}],
        **overrides,
    }
    r = await client.post("/invoices", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_issue_computes_correct_ontario_tax_and_allocates_number():
    client, headers, client_id = await _tenant_with_client(region="ON")
    try:
        draft = await _draft(client, headers, client_id)
        r = await client.post(f"/invoices/{draft['id']}/issue", json={}, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "issued"
        assert data["number"] is not None
        assert data["tax_total"] == "130.00"
        assert data["total"] == "1130.00"
        assert data["tax_treatment_snapshot"] == "taxable"
        assert data["tax_jurisdiction_snapshot"] == "CA-ON"
        assert len(data["tax_lines"]) == 1
        assert data["tax_lines"][0]["tax_type"] == "hst"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_l1_issued_invoice_cannot_be_edited():
    client, headers, client_id = await _tenant_with_client()
    try:
        draft = await _draft(client, headers, client_id)
        await client.post(f"/invoices/{draft['id']}/issue", json={}, headers=headers)

        r = await client.patch(
            f"/invoices/{draft['id']}",
            json={"client_id": client_id, "notes": "sneaky edit"},
            headers=headers,
        )
        assert r.status_code == 409
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_l4_cannot_issue_with_no_line_items():
    client, headers, client_id = await _tenant_with_client()
    try:
        draft = await _draft(client, headers, client_id, line_items=[])
        r = await client.post(f"/invoices/{draft['id']}/issue", json={}, headers=headers)
        assert r.status_code == 422
        assert "line item" in r.json()["detail"].lower()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_l5_zero_total_requires_explicit_confirmation():
    client, headers, client_id = await _tenant_with_client()
    try:
        draft = await _draft(
            client,
            headers,
            client_id,
            line_items=[{"description": "Free", "unit_rate": "0", "amount": "0.00", "is_taxable": False}],
        )
        r = await client.post(f"/invoices/{draft['id']}/issue", json={}, headers=headers)
        assert r.status_code == 422

        r = await client.post(
            f"/invoices/{draft['id']}/issue", json={"confirm_zero_total": True}, headers=headers
        )
        assert r.status_code == 200
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_n1_concurrent_issue_never_produces_duplicate_numbers():
    """edgecases.md N1, P1: two simultaneous issues must never collide."""
    client, headers, client_id = await _tenant_with_client()
    try:
        draft_a = await _draft(client, headers, client_id)
        draft_b = await _draft(client, headers, client_id)

        results = await asyncio.gather(
            client.post(f"/invoices/{draft_a['id']}/issue", json={}, headers=headers),
            client.post(f"/invoices/{draft_b['id']}/issue", json={}, headers=headers),
        )
        numbers = [r.json()["number"] for r in results]
        assert all(r.status_code == 200 for r in results)
        assert len(set(numbers)) == 2, f"duplicate invoice numbers allocated: {numbers}"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_n4_year_rollover_uses_invoice_date_not_issue_date():
    client, headers, client_id = await _tenant_with_client()
    try:
        draft_2025 = await _draft(client, headers, client_id, invoice_date="2025-12-31")
        draft_2026 = await _draft(client, headers, client_id, invoice_date="2026-01-05")

        r_2025 = await client.post(f"/invoices/{draft_2025['id']}/issue", json={}, headers=headers)
        r_2026 = await client.post(f"/invoices/{draft_2026['id']}/issue", json={}, headers=headers)

        assert "2025" in r_2025.json()["number"]
        assert "2026" in r_2026.json()["number"]
        # Both should be the *first* invoice of their respective years.
        assert r_2025.json()["number"].endswith("001")
        assert r_2026.json()["number"].endswith("001")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_n2_failed_issue_does_not_consume_a_number():
    """edgecases.md N2: issue fails after number allocation -> the
    transaction rolls back and the number is not consumed. Here the
    failure is a compliance error (no line items), which is caught before
    allocation ever happens -- verified by checking the next successful
    issue still gets 001, not 002."""
    client, headers, client_id = await _tenant_with_client()
    try:
        empty_draft = await _draft(client, headers, client_id, line_items=[])
        r = await client.post(f"/invoices/{empty_draft['id']}/issue", json={}, headers=headers)
        assert r.status_code == 422

        real_draft = await _draft(client, headers, client_id)
        r = await client.post(f"/invoices/{real_draft['id']}/issue", json={}, headers=headers)
        assert r.status_code == 200
        assert r.json()["number"].endswith("001")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_credit_note_requires_issued_invoice():
    client, headers, client_id = await _tenant_with_client()
    try:
        draft = await _draft(client, headers, client_id)
        r = await client.post(
            f"/invoices/{draft['id']}/credit-note",
            json={"amount": "100.00", "reason": "test"},
            headers=headers,
        )
        assert r.status_code == 404  # not issued yet

        await client.post(f"/invoices/{draft['id']}/issue", json={}, headers=headers)
        r = await client.post(
            f"/invoices/{draft['id']}/credit-note",
            json={"amount": "100.00", "reason": "Overcharged"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        assert "CN" in r.json()["number"]
    finally:
        await client.aclose()
