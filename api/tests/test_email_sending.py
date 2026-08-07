"""User-configured SMTP + invoice email sending. edgecases.md §8 (O1-O10),
implementation_plan.md 2.16-2.17. SMTP calls are monkeypatched -- this
tests that invoices_router/notifications wire things together
correctly, not aiosmtplib's own correctness."""

from uuid import uuid4

import httpx
import pytest

from tallyquo.identity import service
from tallyquo.main import app
from tallyquo.notifications import smtp_client


async def _tenant_with_issued_invoice() -> tuple[httpx.AsyncClient, dict, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"emailsend-{uuid4()}@example.com"
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
            "invoice_date": "2026-05-01",
            "due_date": "2030-01-01",
            "line_items": [{"description": "Work", "unit_rate": "1000.00", "amount": "1000.00"}],
        },
        headers=headers,
    )
    invoice_id = r.json()["id"]
    r = await client.post(f"/invoices/{invoice_id}/issue", json={}, headers=headers)
    assert r.status_code == 200, r.text
    return client, headers, invoice_id


async def _add_account(client: httpx.AsyncClient, headers: dict, **overrides) -> str:
    body = {
        "label": "My Gmail",
        "from_name": "Test Co",
        "from_address": "me@example.com",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_security": "starttls",
        "smtp_username": "me@example.com",
        "password": "app-password",
        **overrides,
    }
    r = await client.post("/email-accounts", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---- email accounts CRUD ------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_list_email_account():
    client, headers, _ = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers)
        r = await client.get("/email-accounts", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["label"] == "My Gmail"
        assert "password" not in r.json()[0]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_second_default_account_unsets_the_first():
    client, headers, _ = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers, label="First", is_default=True)
        await _add_account(client, headers, label="Second", is_default=True)
        r = await client.get("/email-accounts", headers=headers)
        defaults = [a for a in r.json() if a["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["label"] == "Second"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_verify_account_success(monkeypatch):
    async def fake_verify(config):
        return None

    monkeypatch.setattr(smtp_client, "verify", fake_verify)

    client, headers, _ = await _tenant_with_issued_invoice()
    try:
        account_id = await _add_account(client, headers)
        r = await client.post(f"/email-accounts/{account_id}/verify", headers=headers)
        assert r.status_code == 204

        r2 = await client.get("/email-accounts", headers=headers)
        assert r2.json()[0]["verified_at"] is not None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_verify_account_failure_surfaces_message(monkeypatch):
    async def fake_verify(config):
        raise smtp_client.SmtpSendFailed("Authentication failed")

    monkeypatch.setattr(smtp_client, "verify", fake_verify)

    client, headers, _ = await _tenant_with_issued_invoice()
    try:
        account_id = await _add_account(client, headers)
        r = await client.post(f"/email-accounts/{account_id}/verify", headers=headers)
        assert r.status_code == 422
        assert "Authentication failed" in r.json()["detail"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_archive_account_removes_it_from_list():
    client, headers, _ = await _tenant_with_issued_invoice()
    try:
        account_id = await _add_account(client, headers)
        r = await client.delete(f"/email-accounts/{account_id}", headers=headers)
        assert r.status_code == 204

        r2 = await client.get("/email-accounts", headers=headers)
        assert r2.json() == []
    finally:
        await client.aclose()


# ---- sending -------------------------------------------------------------


@pytest.mark.asyncio
async def test_o1_send_requires_explicit_call_and_succeeds(monkeypatch):
    async def fake_send(config, **kwargs):
        return smtp_client.SendResult(accepted=kwargs["to_addresses"] + kwargs["cc_addresses"], refused={})

    monkeypatch.setattr(smtp_client, "send", fake_send)

    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers, is_default=True)
        r = await client.post(
            f"/invoices/{invoice_id}/email",
            data={
                "to_addresses": "client@example.com",
                "cc_addresses": "",
                "subject": "Your invoice",
                "body": "Please find attached.",
                "attach_invoice_pdf": "true",
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "sent"
        assert data["accepted"] == ["client@example.com"]
        assert data["refused"] == {}
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_o10_send_is_logged(monkeypatch):
    async def fake_send(config, **kwargs):
        return smtp_client.SendResult(accepted=kwargs["to_addresses"], refused={})

    monkeypatch.setattr(smtp_client, "send", fake_send)

    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers, is_default=True)
        r = await client.post(
            f"/invoices/{invoice_id}/email",
            data={"to_addresses": "client@example.com", "subject": "Hi", "body": "Body"},
            headers=headers,
        )
        assert r.status_code == 200, r.text

        r2 = await client.get(f"/invoices/{invoice_id}/email-log", headers=headers)
        assert r2.status_code == 200
        assert len(r2.json()) == 1
        assert r2.json()[0]["status"] == "sent"
        assert r2.json()[0]["to_addresses"] == ["client@example.com"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_draft_invoice_cannot_be_emailed(monkeypatch):
    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers, is_default=True)
        # Create a fresh draft on the same tenant.
        r = await client.get(f"/invoices/{invoice_id}", headers=headers)
        client_id = r.json()["client_id"]
        r = await client.post(
            "/invoices",
            json={
                "client_id": client_id,
                "invoice_date": "2026-06-01",
                "line_items": [{"description": "Work", "unit_rate": "1.00", "amount": "1.00"}],
            },
            headers=headers,
        )
        draft_id = r.json()["id"]

        r2 = await client.post(
            f"/invoices/{draft_id}/email",
            data={"to_addresses": "client@example.com", "subject": "Hi", "body": "Body"},
            headers=headers,
        )
        assert r2.status_code == 409
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_o2_no_email_account_configured():
    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        r = await client.post(
            f"/invoices/{invoice_id}/email",
            data={"to_addresses": "client@example.com", "subject": "Hi", "body": "Body"},
            headers=headers,
        )
        assert r.status_code == 422
        assert "email account" in r.json()["detail"].lower()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_no_recipients_rejected():
    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers, is_default=True)
        r = await client.post(
            f"/invoices/{invoice_id}/email",
            data={"to_addresses": "  ", "subject": "Hi", "body": "Body"},
            headers=headers,
        )
        assert r.status_code == 422
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_o8_partial_refusal_returns_200_with_refused_populated(monkeypatch):
    async def fake_send(config, **kwargs):
        return smtp_client.SendResult(accepted=["good@example.com"], refused={"bad@example.com": "mailbox unavailable"})

    monkeypatch.setattr(smtp_client, "send", fake_send)

    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers, is_default=True)
        r = await client.post(
            f"/invoices/{invoice_id}/email",
            data={"to_addresses": "good@example.com,bad@example.com", "subject": "Hi", "body": "Body"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "sent"
        assert data["refused"] == {"bad@example.com": "mailbox unavailable"}
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_total_send_failure_reports_failed_status_and_is_still_logged(monkeypatch):
    async def fake_send(config, **kwargs):
        raise smtp_client.SmtpSendFailed("Connection refused")

    monkeypatch.setattr(smtp_client, "send", fake_send)

    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers, is_default=True)
        r = await client.post(
            f"/invoices/{invoice_id}/email",
            data={"to_addresses": "client@example.com", "subject": "Hi", "body": "Body"},
            headers=headers,
        )
        # A failed send is not an HTTP error -- raising here would roll back
        # the O10 log entry written in the same transaction (see the
        # router's comment). Reported as a normal 200 with status="failed".
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "failed"
        assert "Connection refused" in r.json()["error_detail"]

        # O10: even a failed attempt is logged.
        r2 = await client.get(f"/invoices/{invoice_id}/email-log", headers=headers)
        assert r2.json()[0]["status"] == "failed"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_o5_pdf_unchecked_with_extra_attachment(monkeypatch):
    captured = {}

    async def fake_send(config, **kwargs):
        captured["attachments"] = kwargs.get("attachments") or []
        return smtp_client.SendResult(accepted=kwargs["to_addresses"], refused={})

    monkeypatch.setattr(smtp_client, "send", fake_send)

    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers, is_default=True)
        files = {"extra_files": ("notes.txt", b"hello world", "text/plain")}
        r = await client.post(
            f"/invoices/{invoice_id}/email",
            data={
                "to_addresses": "client@example.com",
                "subject": "Hi",
                "body": "Body",
                "attach_invoice_pdf": "false",
            },
            files=files,
            headers=headers,
        )
        assert r.status_code == 200, r.text

        r2 = await client.get(f"/invoices/{invoice_id}/email-log", headers=headers)
        log = r2.json()[0]
        assert log["attached_invoice_pdf"] is False
        assert log["extra_attachments"] == [{"filename": "notes.txt", "byte_size": 11}]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_o6_oversized_attachment_rejected():
    client, headers, invoice_id = await _tenant_with_issued_invoice()
    try:
        await _add_account(client, headers, is_default=True)
        big = b"x" * (21 * 1024 * 1024)  # over the 20MB cap
        files = {"extra_files": ("big.bin", big, "application/octet-stream")}
        r = await client.post(
            f"/invoices/{invoice_id}/email",
            data={"to_addresses": "client@example.com", "subject": "Hi", "body": "Body"},
            files=files,
            headers=headers,
        )
        assert r.status_code == 422
        assert "size limit" in r.json()["detail"].lower()
    finally:
        await client.aclose()
