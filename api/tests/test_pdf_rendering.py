from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


@pytest.mark.asyncio
async def test_issued_invoice_pdf_is_a_real_pdf():
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        email = f"pdf-{uuid4()}@example.com"
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
                "region_code": "ON",
                "tax_treatment": "taxable",
            },
            headers=headers,
        )
        client_id = r.json()["id"]

        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-06-01",
                "line_items": [
                    {"description": "Consulting", "unit_rate": "1000.00", "amount": "1000.00"}
                ],
            },
            headers=headers,
        )
        invoice_id = r.json()["id"]
        await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)

        r = await client.get(f"/invoices/{invoice_id}/pdf", headers=headers)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"
        assert len(r.content) > 1000
    finally:
        await client.aclose()
