"""Templates: selection, and the portable .json package format.
implementation_plan.md 4.1. Also covers the invoice-issuance template
pin actually reaching PDF rendering, a real pre-existing gap closed in
the same commit as this feature (previously render_pdf always used a
hardcoded accent colour regardless of invoice.template_id)."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _tenant() -> tuple[httpx.AsyncClient, dict]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"templates-{uuid4()}@example.com"
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


VALID_PACKAGE = {
    "package_schema_version": 1,
    "name": "My Custom Template",
    "theme": {"accent_color": "#FF5500", "font_scale": 1.0},
    "blocks": ["supplier", "document", "bill_to", "services", "totals", "payment", "footer"],
}


@pytest.mark.asyncio
async def test_list_templates_returns_three_system_templates():
    client, headers = await _tenant()
    try:
        r = await client.get("/templates", headers=headers)
        assert r.status_code == 200, r.text
        names = {t["name"] for t in r.json()}
        assert names == {"Classic", "Minimal", "Modern"}
        assert all(t["is_system"] for t in r.json())
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_export_system_template_round_trips_through_import():
    client, headers = await _tenant()
    try:
        r = await client.get("/templates", headers=headers)
        classic_id = next(t["id"] for t in r.json() if t["name"] == "Classic")

        r = await client.get(f"/templates/{classic_id}/export", headers=headers)
        assert r.status_code == 200, r.text
        package = r.json()
        assert package["package_schema_version"] == 1
        assert package["name"] == "Classic"
        assert "accent_color" in package["theme"]

        package["name"] = "Classic (copy)"
        r = await client.post("/templates/import", json=package, headers=headers)
        assert r.status_code == 201, r.text
        assert r.json()["name"] == "Classic (copy)"
        assert r.json()["is_system"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_import_valid_package():
    client, headers = await _tenant()
    try:
        r = await client.post("/templates/import", json=VALID_PACKAGE, headers=headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["name"] == "My Custom Template"
        assert data["theme"]["accent_color"] == "#FF5500"
        assert data["is_default"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_import_rejects_unknown_package_schema_version():
    client, headers = await _tenant()
    try:
        bad = {**VALID_PACKAGE, "package_schema_version": 99}
        r = await client.post("/templates/import", json=bad, headers=headers)
        assert r.status_code == 422
        assert "package_schema_version" in r.json()["detail"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_m2_import_rejects_missing_compliance_block():
    """edgecases.md M2: never partially apply a package missing
    compliance-critical content -- reject outright."""
    client, headers = await _tenant()
    try:
        bad = {**VALID_PACKAGE, "blocks": ["supplier", "document", "payment", "footer"]}
        r = await client.post("/templates/import", json=bad, headers=headers)
        assert r.status_code == 422
        assert "compliance" in r.json()["detail"].lower()

        # And it must not have been partially created.
        r = await client.get("/templates", headers=headers)
        assert not any(t["name"] == VALID_PACKAGE["name"] for t in r.json())
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_import_rejects_unknown_block_type():
    client, headers = await _tenant()
    try:
        bad = {**VALID_PACKAGE, "blocks": [*VALID_PACKAGE["blocks"], "raw_html"]}
        r = await client.post("/templates/import", json=bad, headers=headers)
        assert r.status_code == 422
        assert "unknown block" in r.json()["detail"].lower()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_import_rejects_malformed_accent_color():
    client, headers = await _tenant()
    try:
        bad = {**VALID_PACKAGE, "theme": {"accent_color": "orange", "font_scale": 1.0}}
        r = await client.post("/templates/import", json=bad, headers=headers)
        assert r.status_code == 422
        assert "accent_color" in r.json()["detail"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_set_default_template_requires_existing_visible_template():
    client, headers = await _tenant()
    try:
        r = await client.put("/templates/default", json={"template_id": str(uuid4())}, headers=headers)
        assert r.status_code == 404
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_tenant_cannot_see_or_set_another_tenants_private_template():
    """Adversarial RLS check, matching edgecases.md T1/T6: a tenant-scoped
    query never returns another tenant's row, even by exact id."""
    client_a, headers_a = await _tenant()
    client_b, headers_b = await _tenant()
    try:
        r = await client_a.post("/templates/import", json=VALID_PACKAGE, headers=headers_a)
        private_id = r.json()["id"]

        r = await client_b.get("/templates", headers=headers_b)
        assert not any(t["id"] == private_id for t in r.json())

        r = await client_b.put("/templates/default", json={"template_id": private_id}, headers=headers_b)
        assert r.status_code == 404  # never 403 -- existence isn't confirmed
    finally:
        await client_a.aclose()
        await client_b.aclose()


@pytest.mark.asyncio
async def test_chosen_template_theme_reaches_the_rendered_pdf():
    """Regression for the real gap this feature closed: invoice.template_id
    was always pinned, but render_pdf never looked it up -- every PDF
    used the same hardcoded accent colour no matter what. Two invoices
    issued under two different templates must now actually render
    different bytes."""
    client, headers = await _tenant()
    try:
        r = await client.post(
            "/clients",
            json={"legal_name": "Acme", "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
            headers=headers,
        )
        client_id = r.json()["id"]

        async def issue_and_render(accent: str) -> bytes:
            custom = {**VALID_PACKAGE, "name": f"Theme {accent}", "theme": {"accent_color": accent, "font_scale": 1.0}}
            r = await client.post("/templates/import", json=custom, headers=headers)
            template_id = r.json()["id"]
            r = await client.put("/templates/default", json={"template_id": template_id}, headers=headers)
            assert r.status_code == 204

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

            r = await client.get(f"/invoices/{invoice_id}/pdf", headers=headers)
            assert r.status_code == 200
            assert r.headers["content-type"] == "application/pdf"
            return r.content

        pdf_red = await issue_and_render("#FF0000")
        pdf_blue = await issue_and_render("#0000FF")
        assert pdf_red != pdf_blue
    finally:
        await client.aclose()
