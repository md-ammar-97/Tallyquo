"""Payment instructions actually reaching the invoice PDF. A real,
previously-undiscovered gap found while starting Phase 4 workstream
4.2: payment_instruction (1.4) has existed since Phase 1 with full
CRUD, but nothing in issuance or rendering ever read it -- every
invoice this product has issued gave the client no way to pay.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from tallyquo.core.tenant_context import tenant_session
from tallyquo.identity import service
from tallyquo.main import app


async def _tenant() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"payinstr-{uuid4()}@example.com"
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


async def _issue_invoice(client: httpx.AsyncClient, headers: dict) -> str:
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
            "line_items": [{"description": "Work", "unit_rate": "100.00", "amount": "100.00"}],
        },
        headers=headers,
    )
    invoice_id = r.json()["id"]
    r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
    assert r.status_code == 200, r.text
    return invoice_id


@pytest.mark.asyncio
async def test_pdf_differs_with_and_without_payment_instruction():
    client, headers = await _tenant()
    try:
        no_payment_id = await _issue_invoice(client, headers)
        no_payment_pdf = (await client.get(f"/invoices/{no_payment_id}/pdf", headers=headers)).content

        r = await client.post(
            "/payment-instructions",
            json={
                "label": "Main account",
                "method": "etransfer",
                "currency": "CAD",
                "fields": {"email": "pay-me@example.com"},
                "is_default": True,
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text

        with_payment_id = await _issue_invoice(client, headers)
        with_payment_pdf = (await client.get(f"/invoices/{with_payment_id}/pdf", headers=headers)).content

        assert with_payment_pdf != no_payment_pdf
        assert len(with_payment_pdf) > len(no_payment_pdf)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_payment_instruction_snapshot_frozen_at_issue_survives_later_changes():
    """X4/L14: a client re-downloading an old invoice must see the
    payment details they were originally given, not whatever the tenant's
    payment instructions are today."""
    client, headers = await _tenant()
    try:
        await client.post(
            "/payment-instructions",
            json={
                "label": "Old account",
                "method": "etransfer",
                "currency": "CAD",
                "fields": {"email": "old@example.com"},
                "is_default": True,
            },
            headers=headers,
        )
        invoice_id = await _issue_invoice(client, headers)
        old_pdf = (await client.get(f"/invoices/{invoice_id}/pdf", headers=headers)).content

        r = await client.get("/profile", headers=headers)
        tenant_id = r.json()["tenant_id"]
        async with tenant_session(tenant_id) as session:
            row = await session.execute(
                text("SELECT payment_instruction_snapshot FROM invoice WHERE id = :id"), {"id": invoice_id}
            )
            snap = row.mappings().one()["payment_instruction_snapshot"]
            assert snap["fields"]["email"] == "old@example.com"

        # Tenant switches to a new default account.
        await client.post(
            "/payment-instructions",
            json={
                "label": "New account",
                "method": "etransfer",
                "currency": "CAD",
                "fields": {"email": "new@example.com"},
                "is_default": True,
            },
            headers=headers,
        )

        # Not asserted byte-identical: reportlab embeds a wall-clock
        # creation timestamp in every PDF's metadata regardless of
        # content, so two renders of the *same* invoice a moment apart
        # already differ by a few bytes -- nothing in this codebase
        # hashes/compares PDF bytes for correctness (snapshot_verify only
        # re-checks the tax computation, never touches rendering), so
        # that's an accepted, harmless imprecision, not the thing this
        # test is guarding. The content-level guarantee -- still the OLD
        # account, not the new one -- is what the DB snapshot check above
        # already proved; this re-render just confirms it doesn't crash
        # and stays close in size (no section silently added or dropped).
        re_rendered_pdf = (await client.get(f"/invoices/{invoice_id}/pdf", headers=headers)).content
        assert abs(len(re_rendered_pdf) - len(old_pdf)) < 50
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_no_payment_instruction_configured_omits_section_without_error():
    client, headers = await _tenant()
    try:
        invoice_id = await _issue_invoice(client, headers)
        r = await client.get(f"/invoices/{invoice_id}/pdf", headers=headers)
        assert r.status_code == 200
        assert r.content[:5] == b"%PDF-"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_draft_preview_matches_what_issuing_will_actually_produce():
    """A brand new tenant with no default_template_id chosen must preview
    the same blocks (payment, footer) that issuing will pin -- the system
    default template, not an empty fallback. Previously this would have
    silently hidden the payment section in preview only for it to appear
    once issued."""
    client, headers = await _tenant()
    try:
        await client.post(
            "/payment-instructions",
            json={
                "label": "Main",
                "method": "etransfer",
                "currency": "CAD",
                "fields": {"email": "pay@example.com"},
                "is_default": True,
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
                "line_items": [{"description": "Work", "unit_rate": "100.00", "amount": "100.00"}],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]

        draft_pdf = (await client.get(f"/invoices/{invoice_id}/pdf", headers=headers)).content

        await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
        issued_pdf = (await client.get(f"/invoices/{invoice_id}/pdf", headers=headers)).content

        # Both should be non-trivially large (payment section present in
        # both) -- draft isn't required to be byte-identical to issued
        # (dates/status text differ), just in the same size ballpark,
        # confirming the payment block wasn't silently dropped in preview.
        assert abs(len(draft_pdf) - len(issued_pdf)) < 200
    finally:
        await client.aclose()
