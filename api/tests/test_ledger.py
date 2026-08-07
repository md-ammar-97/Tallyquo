from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app


async def _setup() -> tuple[httpx.AsyncClient, dict, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"ledger-{uuid4()}@example.com"
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
    return client, headers, client_id


@pytest.mark.asyncio
async def test_ledger_filters_by_status_and_date():
    client, headers, client_id = await _setup()
    try:
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-01-15",
                "line_items": [{"description": "A", "unit_rate": "100", "amount": "100.00"}],
            },
            headers=headers,
        )
        issued_id = r.json()["id"]
        await client.post(f"/invoices/{issued_id}/issue", json={}, headers=headers)

        await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-02-15",
                "line_items": [{"description": "B", "unit_rate": "200", "amount": "200.00"}],
            },
            headers=headers,
        )

        r = await client.get("/invoices", params={"status": "issued"}, headers=headers)
        assert len(r.json()) == 1
        assert r.json()[0]["id"] == issued_id

        r = await client.get("/invoices", params={"status": "draft"}, headers=headers)
        assert len(r.json()) == 1

        r = await client.get(
            "/invoices", params={"date_from": "2026-02-01", "date_to": "2026-02-28"}, headers=headers
        )
        assert len(r.json()) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_ledger_csv_export():
    client, headers, client_id = await _setup()
    try:
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-03-01",
                "line_items": [{"description": "A", "unit_rate": "100", "amount": "100.00"}],
            },
            headers=headers,
        )
        await client.post(f"/invoices/{r.json()['id']}/issue", json={}, headers=headers)

        r = await client.get("/invoices/export.csv", headers=headers)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        lines = r.text.strip().splitlines()
        assert lines[0].startswith("number,status")
        assert len(lines) == 2
    finally:
        await client.aclose()
