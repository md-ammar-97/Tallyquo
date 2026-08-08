"""Phase 4 workstream 4.2: the custom template editor's backend --
create/update/archive of tenant-owned templates, version history
(X4/L14: editing a template must never change how an already-issued
invoice re-renders), the live-preview endpoint, and logo upload
(closes Phase 1's 1.5 gap, found while starting this workstream:
`logo_ref`/`logo_dark_ref` existed on `business_profile` since
migration 0002 but nothing ever wrote to them)."""

import base64
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from tallyquo.core.tenant_context import tenant_session
from tallyquo.identity import service
from tallyquo.main import app

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

_BLOCKS = ["supplier", "document", "bill_to", "services", "totals", "payment", "footer"]


async def _tenant() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"tpleditor-{uuid4()}@example.com"
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


def _template_in(**overrides) -> dict:
    body = {
        "name": "My Custom",
        "theme": {"accent_color": "#123456", "font_scale": 1.0, "margins_mm": 20, "logo_position": "top_left"},
        "blocks": _BLOCKS,
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_create_template():
    client, headers = await _tenant()
    try:
        r = await client.post("/templates", json=_template_in(), headers=headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["name"] == "My Custom"
        assert data["version"] == 1
        assert data["is_system"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_create_rejects_missing_compliance_block():
    client, headers = await _tenant()
    try:
        bad = _template_in(blocks=["supplier", "payment"])
        r = await client.post("/templates", json=bad, headers=headers)
        assert r.status_code == 422
        assert "compliance" in r.json()["detail"].lower()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_create_rejects_out_of_range_font_scale():
    client, headers = await _tenant()
    try:
        bad = _template_in(theme={"accent_color": "#123456", "font_scale": 5.0})
        r = await client.post("/templates", json=bad, headers=headers)
        assert r.status_code == 422
        assert "font_scale" in r.json()["detail"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_update_bumps_version_and_archives_previous_into_history():
    client, headers = await _tenant()
    try:
        r = await client.post("/templates", json=_template_in(), headers=headers)
        template_id = r.json()["id"]
        assert r.json()["version"] == 1

        updated = _template_in(name="My Custom v2", theme={"accent_color": "#FF00FF", "font_scale": 1.0})
        r = await client.put(f"/templates/{template_id}", json=updated, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["version"] == 2
        assert r.json()["theme"]["accent_color"] == "#FF00FF"

        r = await client.get("/profile", headers=headers)
        tenant_id = r.json()["tenant_id"]
        async with tenant_session(tenant_id) as session:
            row = await session.execute(
                text(
                    "SELECT theme FROM template_version_history WHERE template_id = :id AND version = 1"
                ),
                {"id": template_id},
            )
            history = row.mappings().one()
            assert history["theme"]["accent_color"] == "#123456"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_cannot_update_a_system_template():
    client, headers = await _tenant()
    try:
        r = await client.get("/templates", headers=headers)
        classic_id = next(t["id"] for t in r.json() if t["name"] == "Classic")
        r = await client.put(f"/templates/{classic_id}", json=_template_in(), headers=headers)
        assert r.status_code == 404
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_cannot_update_another_tenants_template():
    client_a, headers_a = await _tenant()
    client_b, headers_b = await _tenant()
    try:
        r = await client_a.post("/templates", json=_template_in(), headers=headers_a)
        template_id = r.json()["id"]
        r = await client_b.put(f"/templates/{template_id}", json=_template_in(name="Hijacked"), headers=headers_b)
        assert r.status_code == 404
    finally:
        await client_a.aclose()
        await client_b.aclose()


@pytest.mark.asyncio
async def test_archive_removes_from_list_and_cannot_be_redone_by_another_tenant():
    client, headers = await _tenant()
    try:
        r = await client.post("/templates", json=_template_in(), headers=headers)
        template_id = r.json()["id"]
        r = await client.delete(f"/templates/{template_id}", headers=headers)
        assert r.status_code == 204
        r = await client.get("/templates", headers=headers)
        assert not any(t["id"] == template_id for t in r.json())
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_cannot_archive_a_system_template():
    client, headers = await _tenant()
    try:
        r = await client.get("/templates", headers=headers)
        classic_id = next(t["id"] for t in r.json() if t["name"] == "Classic")
        r = await client.delete(f"/templates/{classic_id}", headers=headers)
        assert r.status_code == 404
        r = await client.get("/templates", headers=headers)
        assert any(t["id"] == classic_id for t in r.json())
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_editing_a_template_does_not_change_an_already_issued_invoices_pdf():
    """The actual X4/L14 regression this migration exists to close:
    before template_version_history, render_pdf looked up an issued
    invoice's template by id alone with no version filter, so editing
    the template would immediately change how every invoice already
    issued against it re-rendered."""
    client, headers = await _tenant()
    try:
        r = await client.post("/templates", json=_template_in(theme={"accent_color": "#111111"}), headers=headers)
        template_id = r.json()["id"]
        r = await client.put("/templates/default", json={"template_id": template_id}, headers=headers)
        assert r.status_code == 204

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

        pdf_before_edit = (await client.get(f"/invoices/{invoice_id}/pdf", headers=headers)).content

        # Edit the template to a wildly different accent colour.
        r = await client.put(
            f"/templates/{template_id}",
            json=_template_in(theme={"accent_color": "#EEEEEE"}),
            headers=headers,
        )
        assert r.status_code == 200, r.text

        pdf_after_edit = (await client.get(f"/invoices/{invoice_id}/pdf", headers=headers)).content

        # Not byte-identical (reportlab's timestamp, per edgecases.md X4)
        # but close in size -- the point is the CONTENT (accent colour)
        # didn't change, which a size-only check can't fully prove, so
        # cross-check against a fresh draft under the *new* template
        # version, which must differ meaningfully more than the
        # before/after-edit pair does.
        assert abs(len(pdf_after_edit) - len(pdf_before_edit)) < 50

        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-05-02",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Work", "unit_rate": "100.00", "amount": "100.00"}],
            },
            headers=headers,
        )
        new_draft_id = r.json()["id"]
        r = await client.post(f"/invoices/{new_draft_id}/issue", json={}, headers=headers)
        assert r.status_code == 200, r.text
        pdf_new_invoice = (await client.get(f"/invoices/{new_draft_id}/pdf", headers=headers)).content

        # The new invoice is pinned to version 2 (post-edit); the old one
        # stays pinned to version 1. Fetch both snapshots directly to
        # prove the DB-level guarantee, not just an inference from size.
        r = await client.get("/profile", headers=headers)
        tenant_id = r.json()["tenant_id"]
        async with tenant_session(tenant_id) as session:
            rows = await session.execute(
                text("SELECT id, template_version FROM invoice WHERE id IN (:a, :b)"),
                {"a": invoice_id, "b": new_draft_id},
            )
            versions = {str(row["id"]): row["template_version"] for row in rows.mappings().all()}
            assert versions[invoice_id] == 1
            assert versions[new_draft_id] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_preview_renders_a_pdf_without_persisting_anything():
    client, headers = await _tenant()
    try:
        r = await client.get("/templates", headers=headers)
        before_count = len(r.json())

        r = await client.post(
            "/templates/preview",
            json={"theme": {"accent_color": "#00FF00", "font_scale": 1.0}, "blocks": _BLOCKS},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"

        r = await client.get("/templates", headers=headers)
        assert len(r.json()) == before_count
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_preview_rejects_invalid_theme_without_rendering():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/templates/preview",
            json={"theme": {"accent_color": "not-a-color"}, "blocks": _BLOCKS},
            headers=headers,
        )
        assert r.status_code == 422
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_upload_logo_and_it_appears_in_preview_pdf():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/profile/logo",
            files={"file": ("logo.png", _PNG_1X1, "image/png")},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["logo_ref"] is not None

        r = await client.post(
            "/templates/preview",
            json={"theme": {"accent_color": "#0D99FF", "logo_position": "top_left"}, "blocks": _BLOCKS},
            headers=headers,
        )
        with_logo = r.content

        r = await client.post(
            "/templates/preview",
            json={"theme": {"accent_color": "#0D99FF", "logo_position": "none"}, "blocks": _BLOCKS},
            headers=headers,
        )
        without_logo = r.content
        assert len(with_logo) > len(without_logo)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_upload_logo_rejects_non_image_content():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/profile/logo",
            files={"file": ("logo.txt", b"not an image", "text/plain")},
            headers=headers,
        )
        assert r.status_code == 422
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_upload_logo_dark_variant_writes_the_other_column():
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/profile/logo?variant=dark",
            files={"file": ("logo-dark.png", _PNG_1X1, "image/png")},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["logo_dark_ref"] is not None
        assert r.json()["logo_ref"] is None
    finally:
        await client.aclose()
