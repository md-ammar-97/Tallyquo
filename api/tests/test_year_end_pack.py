"""Year-end accountant pack. implementation_plan.md 3.11.

Storage isn't configured against real credentials in this test
environment (api/.env: "keys aren't generated yet") -- every test here
monkeypatches tallyquo.core.storage's functions directly, the same way
test_email_sending.py monkeypatches smtp_client rather than hitting a
real mail server for the parts that aren't the thing under test.
"""

import io
import zipfile
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from tallyquo.core.tenant_context import tenant_session
from tallyquo.exports import year_end_service
from tallyquo.identity import service
from tallyquo.main import app


async def _tenant_with_data() -> tuple[httpx.AsyncClient, dict, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"yearend-{uuid4()}@example.com"
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
        json={"legal_name": "Acme", "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
        headers=headers,
    )
    client_id = r.json()["id"]
    r = await client.post(
        "/invoices",
        json={
            "client_id": client_id,
            "invoice_date": "2026-03-15",
            "due_date": "2030-01-01",
            "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
        },
        headers=headers,
    )
    invoice_id = r.json()["id"]
    r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
    assert r.status_code == 200, r.text

    r = await client.post(
        "/expenses",
        json={"expense_date": "2026-04-01", "vendor": "Staples", "amount_total": "113.00", "tax_amount": "13.00"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    expense_id = r.json()["id"]

    return client, headers, expense_id


@pytest.mark.asyncio
async def test_year_end_pack_requires_business_profile():
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        email = f"yearend-noprofile-{uuid4()}@example.com"
        code = await service.request_otp(email, ip=None)
        r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await client.post("/exports/year-end?year=2026", headers=headers)
        assert r.status_code == 422
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_year_end_pack_storage_failure_is_a_clean_error(monkeypatch):
    """A storage-layer failure (real credentials misconfigured, network
    blip, quota) must surface as a clean 502, not an unhandled 500 that
    a browser reports as an opaque CORS failure -- caught by hand while
    verifying this feature in a browser against local dev, where
    storage genuinely isn't configured yet."""
    import botocore.exceptions

    def _boom(*args, **kwargs):
        raise botocore.exceptions.ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "PutObject")

    monkeypatch.setattr(year_end_service.storage, "upload_generated", _boom)

    client, headers, _ = await _tenant_with_data()
    try:
        r = await client.post("/exports/year-end?year=2026", headers=headers)
        assert r.status_code == 502
        assert "temporarily unavailable" in r.json()["detail"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_year_end_pack_contains_expected_entries(monkeypatch):
    monkeypatch.setattr(
        year_end_service.storage, "upload_generated", lambda tenant_id, parts, data, content_type: "fake/key.zip"
    )
    monkeypatch.setattr(year_end_service.storage, "signed_url", lambda key, ttl_seconds=None: "https://example.com/fake-signed-url")

    client, headers, _ = await _tenant_with_data()
    try:
        r = await client.post("/exports/year-end?year=2026", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["url"] == "https://example.com/fake-signed-url"
        assert data["filename"] == "tallyquo-year-end-2026.zip"
        assert data["expires_in_seconds"] == 7 * 24 * 60 * 60
        assert data["byte_size"] > 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_year_end_pack_zip_contents_directly():
    """Builds the pack via the service function (not the HTTP layer) so
    the actual zip bytes can be inspected entry by entry."""
    client, headers, expense_id = await _tenant_with_data()
    try:
        r = await client.get("/profile", headers=headers)
        tenant_id = r.json()["tenant_id"]

        async with tenant_session(tenant_id) as session:
            # Plant a receipt row directly -- no real storage upload needed
            # to exercise the "receipts get bundled" path.
            receipt_id = uuid4()
            await session.execute(
                text(
                    "INSERT INTO receipt (id, tenant_id, expense_id, file_ref, file_hash, mime_type, byte_size) "
                    "VALUES (:id, :tenant_id, :expense_id, :file_ref, :file_hash, :mime_type, :byte_size)"
                ),
                {
                    "id": receipt_id,
                    "tenant_id": tenant_id,
                    "expense_id": expense_id,
                    "file_ref": f"{tenant_id}/receipts/fake.jpg",
                    "file_hash": b"\x00" * 32,
                    "mime_type": "image/jpeg",
                    "byte_size": 4,
                },
            )
            import tallyquo.exports.year_end_service as yes

            original_download = yes.storage.download
            yes.storage.download = lambda key: b"\xff\xd8\xff\xd9"  # minimal JPEG-ish bytes
            try:
                pack_bytes = await yes.build_year_end_pack(session, tenant_id, 2026)
            finally:
                yes.storage.download = original_download

        zf = zipfile.ZipFile(io.BytesIO(pack_bytes))
        names = zf.namelist()

        assert any(n.startswith("invoices/") and n.endswith(".pdf") for n in names)
        assert "expenses.csv" in names
        assert "gst_hst_summary.csv" in names
        assert "profit_and_loss.csv" in names
        assert "README.txt" in names
        assert any(n.startswith("receipts/") for n in names)

        expenses_csv = zf.read("expenses.csv").decode("utf-8")
        assert "Staples" in expenses_csv
        assert "113.00" in expenses_csv

        gst_csv = zf.read("gst_hst_summary.csv").decode("utf-8")
        assert "2026-Q1" in gst_csv

        readme = zf.read("README.txt").decode("utf-8")
        assert "not tax advice" in readme
        assert "Test Co" in readme
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_year_end_pack_excludes_draft_invoices():
    client, headers, _ = await _tenant_with_data()
    try:
        r = await client.get("/profile", headers=headers)
        tenant_id = r.json()["tenant_id"]

        r = await client.post(
            "/clients",
            json={"legal_name": "Acme2", "country_code": "CA", "region_code": "ON", "tax_treatment": "taxable"},
            headers=headers,
        )
        r = await client.post(
            "/invoices",
            json={
                "client_id": r.json()["id"],
                "invoice_date": "2026-05-01",
                "due_date": "2030-01-01",
                "line_items": [{"description": "Draft work", "unit_rate": "1.00", "amount": "1.00"}],
            },
            headers=headers,
        )
        assert r.status_code == 201  # never issued -- stays draft

        async with tenant_session(tenant_id) as session:
            pack_bytes = await year_end_service.build_year_end_pack(session, tenant_id, 2026)

        zf = zipfile.ZipFile(io.BytesIO(pack_bytes))
        invoice_entries = [n for n in zf.namelist() if n.startswith("invoices/")]
        assert len(invoice_entries) == 1  # only the one issued invoice, not the draft
    finally:
        await client.aclose()
