"""GET /invoices/:id/document, POST /invoices/preview-document, and
GET /public/invoices/:token/document -- Phase E of the Sovereign
Ledger redesign. assemble_invoice_document extracts render_pdf's data
assembly (draft-vs-issued branching, template pin resolution with the
template_version_history fallback, payment-instruction/logo rules)
into a function shared by the PDF renderer and this new web-rendered
document preview, so the two can never drift apart. The PDF regression
suite (test_pdf_rendering.py, test_pdf_renderer_theme.py) already
proves the extraction didn't change PDF output -- this file covers the
new JSON surface itself."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"invoicedoc-{uuid4()}@example.com"
    code = await service.request_otp(email, ip=None)
    r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    await client.patch(
        "/profile",
        json={
            "legal_name": "Doc Test Co",
            "address_line1": "1 Main St",
            "city": "Toronto",
            "region_code": "ON",
            "postal_code": "M5V 1A1",
        },
        headers=headers,
    )
    return client, headers


async def _client_id(client: httpx.AsyncClient, headers: dict, name: str = "Acme") -> str:
    r = await client.post(
        "/clients",
        json={"legal_name": name, "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_preview_document_reflects_live_draft_data_without_persisting():
    client, headers = await _tenant()
    try:
        client_id = await _client_id(client, headers)
        r = await client.get("/clients", headers=headers)
        before_count = len(r.json())

        r = await client.post(
            "/invoices/preview-document",
            json={
                "client_id": client_id,
                "invoice_date": "2026-05-01",
                "line_items": [{"description": "Design work", "unit_rate": "500.00", "amount": "500.00"}],
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["invoice"]["number"] is None
        assert doc["invoice"]["subtotal"] == "500.00"
        assert doc["invoice"]["line_items"][0]["description"] == "Design work"
        assert doc["supplier"]["legal_name"] == "Doc Test Co"
        assert doc["client"]["legal_name"] == "Acme"

        r = await client.get("/invoices", headers=headers)
        assert r.json() == []
        r = await client.get("/clients", headers=headers)
        assert len(r.json()) == before_count
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_preview_document_requires_business_profile():
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        email = f"invoicedoc-noprofile-{uuid4()}@example.com"
        code = await service.request_otp(email, ip=None)
        r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await client.post(
            "/invoices/preview-document",
            json={"client_id": str(uuid4()), "line_items": []},
            headers=headers,
        )
        assert r.status_code == 422
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_preview_document_404s_for_unknown_client():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/invoices/preview-document",
            json={"client_id": str(uuid4()), "line_items": []},
            headers=headers,
        )
        assert r.status_code == 404
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_draft_document_endpoint_matches_preview_shape():
    client, headers = await _tenant()
    try:
        client_id = await _client_id(client, headers)
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-05-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "100.00", "amount": "100.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]

        r = await client.get(f"/invoices/{invoice_id}/document", headers=headers)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["invoice"]["number"] is None
        assert doc["invoice"]["subtotal"] == "100.00"
        assert doc["client"]["legal_name"] == "Acme"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_issued_invoice_document_uses_frozen_snapshot_not_live_profile():
    """Same X4/L14 freeze guarantee as the PDF: a re-fetch of an
    already-issued invoice's document must keep showing the supplier
    details the client was originally given, even after the business
    profile changes afterward."""
    client, headers = await _tenant()
    try:
        client_id = await _client_id(client, headers)
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-05-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "100.00", "amount": "100.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        assert r.status_code == 200, r.text

        r = await client.get(f"/invoices/{invoice_id}/document", headers=headers)
        assert r.json()["supplier"]["legal_name"] == "Doc Test Co"
        assert r.json()["invoice"]["number"] == "INV-2026-001"

        await client.patch("/profile", json={"legal_name": "Renamed Co"}, headers=headers)

        r = await client.get(f"/invoices/{invoice_id}/document", headers=headers)
        assert r.json()["supplier"]["legal_name"] == "Doc Test Co"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_public_document_matches_authenticated_document():
    client, headers = await _tenant()
    try:
        client_id = await _client_id(client, headers)
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-05-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "250.00", "amount": "250.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)

        r = await client.post(f"/invoices/{invoice_id}/share", headers=headers)
        assert r.status_code == 200, r.text
        token = r.json()["token"]

        r = await client.get(f"/public/invoices/{token}/document")
        assert r.status_code == 200, r.text
        assert r.json()["invoice"]["subtotal"] == "250.00"
        assert r.json()["client"]["legal_name"] == "Acme"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_document_endpoint_404s_for_unknown_invoice():
    client, headers = await _tenant()
    try:
        r = await client.get(f"/invoices/{uuid4()}/document", headers=headers)
        assert r.status_code == 404
    finally:
        await client.aclose()
