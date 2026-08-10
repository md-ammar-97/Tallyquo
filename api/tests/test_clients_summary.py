"""GET /clients/summary -- Phase C of the Sovereign Ledger redesign.

Powers the redesigned Clients list (Outstanding column + pagination).
Deliberately not rollup_service.tenant_aging_report, which only
includes clients with an *overdue* balance and drops zero-outstanding
clients entirely -- this endpoint must return every client."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _authed_client() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"clientssummary-{uuid4()}@example.com"
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


async def _create_client(client: httpx.AsyncClient, headers: dict, name: str) -> str:
    r = await client.post(
        "/clients",
        json={"legal_name": name, "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _issue_invoice(
    client: httpx.AsyncClient, headers: dict, client_id: str, due_date: str, invoice_date: str = "2026-01-01"
) -> str:
    r = await client.post(
        "/invoices",
        json={
            "client_id": client_id,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    invoice_id = r.json()["id"]
    r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
    assert r.status_code == 200, r.text
    return invoice_id


@pytest.mark.asyncio
async def test_pagination_and_total_count():
    client, headers = await _authed_client()
    try:
        for i in range(3):
            await _create_client(client, headers, f"Client {i}")

        r = await client.get("/clients/summary?limit=2&offset=0", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2

        r = await client.get("/clients/summary?limit=2&offset=2", headers=headers)
        data = r.json()
        assert len(data["items"]) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_zero_outstanding_client_still_appears():
    client, headers = await _authed_client()
    try:
        await _create_client(client, headers, "No Invoices Co")
        r = await client.get("/clients/summary", headers=headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["outstanding_cad"] == "0.00" or float(items[0]["outstanding_cad"]) == 0.0
        assert items[0]["has_overdue"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_not_yet_due_unpaid_invoice_counts_as_outstanding_without_overdue():
    client, headers = await _authed_client()
    try:
        client_id = await _create_client(client, headers, "Future Due Co")
        await _issue_invoice(client, headers, client_id, due_date="2030-01-01")

        r = await client.get("/clients/summary", headers=headers)
        items = r.json()["items"]
        assert len(items) == 1
        assert float(items[0]["outstanding_cad"]) == 1000.0
        assert items[0]["has_overdue"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_overdue_unpaid_invoice_sets_has_overdue():
    client, headers = await _authed_client()
    try:
        client_id = await _create_client(client, headers, "Overdue Co")
        await _issue_invoice(client, headers, client_id, invoice_date="2020-01-01", due_date="2020-02-01")

        r = await client.get("/clients/summary", headers=headers)
        items = r.json()["items"]
        assert len(items) == 1
        assert float(items[0]["outstanding_cad"]) == 1000.0
        assert items[0]["has_overdue"] is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_fully_paid_invoice_drops_outstanding_to_zero():
    client, headers = await _authed_client()
    try:
        client_id = await _create_client(client, headers, "Paid Co")
        invoice_id = await _issue_invoice(client, headers, client_id, due_date="2030-01-01")

        r = await client.post(
            f"/invoices/{invoice_id}/payments",
            json={"amount": "1000.00", "received_date": "2026-01-05"},
            headers=headers,
        )
        assert r.status_code == 201, r.text

        r = await client.get("/clients/summary", headers=headers)
        items = r.json()["items"]
        assert len(items) == 1
        assert float(items[0]["outstanding_cad"]) == 0.0
        assert items[0]["has_overdue"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_summary_excludes_archived_clients():
    client, headers = await _authed_client()
    try:
        client_id = await _create_client(client, headers, "To Archive Co")
        r = await client.delete(f"/clients/{client_id}", headers=headers)
        assert r.status_code == 204

        r = await client.get("/clients/summary", headers=headers)
        assert r.json()["total"] == 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_summary_is_tenant_scoped():
    """Adversarial RLS check, matching this codebase's established
    pattern (edgecases.md T1/T6): one tenant's clients/invoices must
    never leak into another tenant's summary."""
    client_a, headers_a = await _authed_client()
    client_b, headers_b = await _authed_client()
    try:
        await _create_client(client_a, headers_a, "Tenant A Client")
        r = await client_b.get("/clients/summary", headers=headers_b)
        assert r.json()["total"] == 0
    finally:
        await client_a.aclose()
        await client_b.aclose()
