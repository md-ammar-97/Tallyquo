"""Recurring invoices. implementation_plan.md 2.6-2.7, edgecases.md R1-R12."""

from datetime import date, timedelta
from uuid import uuid4

import httpx
import pytest

from tallyquo.billing.recurring_service import generate_due_occurrences, next_occurrence
from tallyquo.identity import service
from tallyquo.main import app


async def _tenant_with_source_invoice(*, amount: str = "1000.00") -> tuple[httpx.AsyncClient, dict, str, str]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    email = f"recurring-{uuid4()}@example.com"
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
            "invoice_date": "2026-01-01",
            "due_date": "2030-01-01",
            "line_items": [{"description": "Retainer", "unit_rate": amount, "amount": amount}],
        },
        headers=headers,
    )
    invoice_id = r.json()["id"]
    return client, headers, client_id, invoice_id


# ---- pure clamping logic (R1, R2) --------------------------------------


def test_r1_monthly_clamps_to_shorter_month():
    result = next_occurrence("monthly", 31, date(2026, 1, 31))
    assert result == date(2026, 2, 28)  # 2026 is not a leap year


def test_r2_feb_29_clamps_on_non_leap_year():
    result = next_occurrence("annual", 29, date(2028, 2, 29))  # 2028 is a leap year
    assert result == date(2029, 2, 28)


def test_weekly_adds_seven_days():
    assert next_occurrence("weekly", None, date(2026, 3, 4)) == date(2026, 3, 11)


# ---- rule CRUD ----------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_get_rule():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice()
    try:
        r = await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "day_of_period": 1,
                "next_run_date": "2026-02-01",
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text
        rule_id = r.json()["id"]

        r2 = await client.get(f"/recurring/{rule_id}", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["cadence"] == "monthly"
        assert r2.json()["is_paused"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rejects_invalid_cadence():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice()
    try:
        r = await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "daily",
                "next_run_date": "2026-02-01",
            },
            headers=headers,
        )
        assert r.status_code == 422
    finally:
        await client.aclose()


# ---- generation -----------------------------------------------------------


@pytest.mark.asyncio
async def test_generates_draft_due_today():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice()
    try:
        today = date.today()
        r = await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "day_of_period": today.day,
                "next_run_date": today.isoformat(),
            },
            headers=headers,
        )
        rule_id = r.json()["id"]

        await generate_due_occurrences()

        r2 = await client.get(f"/recurring/{rule_id}", headers=headers)
        assert r2.json()["last_run_date"] == today.isoformat()
        assert date.fromisoformat(r2.json()["next_run_date"]) > today

        r3 = await client.get("/invoices", params={"client_id": client_id}, headers=headers)
        drafts = [i for i in r3.json() if i["status"] == "draft" and i["id"] != invoice_id]
        assert len(drafts) == 1
        assert drafts[0]["line_items"] == [] or True  # populated via detail fetch below
        detail = await client.get(f"/invoices/{drafts[0]['id']}", headers=headers)
        assert detail.json()["line_items"][0]["description"] == "Retainer"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_r3_idempotent_on_repeated_runs():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice()
    try:
        today = date.today()
        await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "next_run_date": today.isoformat(),
            },
            headers=headers,
        )

        await generate_due_occurrences()
        await generate_due_occurrences()  # second run must not double-generate

        r = await client.get("/invoices", params={"client_id": client_id}, headers=headers)
        drafts = [i for i in r.json() if i["status"] == "draft" and i["id"] != invoice_id]
        assert len(drafts) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_r4_backfills_missed_occurrences_with_original_dates():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice()
    try:
        # Rule hasn't run in ~3 months -- job outage simulation.
        start = date.today() - timedelta(days=95)
        await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "day_of_period": start.day,
                "next_run_date": start.isoformat(),
            },
            headers=headers,
        )

        await generate_due_occurrences()

        r = await client.get("/invoices", params={"client_id": client_id}, headers=headers)
        drafts = [i for i in r.json() if i["status"] == "draft" and i["id"] != invoice_id]
        # At minimum the original occurrence plus a following month -- exact
        # count depends on today's date, so assert >= 2 rather than a fixed N.
        assert len(drafts) >= 2
        dates = sorted(d["invoice_date"] for d in drafts)
        assert dates[0] == start.isoformat()  # first backfilled occurrence keeps its ORIGINAL date
        assert dates[0] < date.today().isoformat()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_r5_archived_client_auto_pauses_rule():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice()
    try:
        today = date.today()
        r = await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "next_run_date": today.isoformat(),
            },
            headers=headers,
        )
        rule_id = r.json()["id"]

        await client.delete(f"/clients/{client_id}", headers=headers)  # archive
        await generate_due_occurrences()

        r2 = await client.get(f"/recurring/{rule_id}", headers=headers)
        assert r2.json()["is_paused"] is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_r8_auto_issue_falls_back_to_draft_on_compliance_failure():
    # Zero-amount source line item forces issue_invoice's zero-total
    # compliance gate (confirm_zero_total is hardcoded False for
    # auto-issue) -- P1: never auto-issue a non-compliant invoice.
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice(amount="0.00")
    try:
        today = date.today()
        await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "next_run_date": today.isoformat(),
                "auto_issue": True,
            },
            headers=headers,
        )

        await generate_due_occurrences()

        r = await client.get("/invoices", params={"client_id": client_id}, headers=headers)
        generated = [i for i in r.json() if i["id"] != invoice_id]
        assert len(generated) == 1
        assert generated[0]["status"] == "draft"  # never auto-issued despite auto_issue=true
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_auto_issue_succeeds_when_compliant():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice(amount="500.00")
    try:
        today = date.today()
        await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "next_run_date": today.isoformat(),
                "auto_issue": True,
            },
            headers=headers,
        )

        await generate_due_occurrences()

        r = await client.get("/invoices", params={"client_id": client_id}, headers=headers)
        generated = [i for i in r.json() if i["id"] != invoice_id]
        assert len(generated) == 1
        assert generated[0]["status"] == "issued"
        assert generated[0]["number"] is not None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_r9_occurrences_remaining_reaches_zero_archives_rule():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice()
    try:
        today = date.today()
        r = await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "next_run_date": today.isoformat(),
                "occurrences_remaining": 1,
            },
            headers=headers,
        )
        rule_id = r.json()["id"]

        await generate_due_occurrences()

        r2 = await client.get(f"/recurring/{rule_id}", headers=headers)
        assert r2.json()["is_paused"] is True
        assert r2.json()["occurrences_remaining"] == 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_skip_next_advances_without_generating():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice()
    try:
        r = await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "day_of_period": 15,
                "next_run_date": "2026-05-15",
            },
            headers=headers,
        )
        rule_id = r.json()["id"]

        r2 = await client.post(f"/recurring/{rule_id}/skip", headers=headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["next_run_date"] == "2026-06-15"

        r3 = await client.get("/invoices", params={"client_id": client_id}, headers=headers)
        assert len([i for i in r3.json() if i["id"] != invoice_id]) == 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_pause_and_resume():
    client, headers, client_id, invoice_id = await _tenant_with_source_invoice()
    try:
        r = await client.post(
            "/recurring",
            json={
                "client_id": client_id,
                "source_invoice_id": invoice_id,
                "cadence": "monthly",
                "next_run_date": "2026-01-01",
            },
            headers=headers,
        )
        rule_id = r.json()["id"]

        r2 = await client.post(f"/recurring/{rule_id}/pause", headers=headers)
        assert r2.json()["is_paused"] is True

        r3 = await client.post(f"/recurring/{rule_id}/resume", headers=headers)
        assert r3.json()["is_paused"] is False
        # R10: resumed to the next future occurrence, not backfilled to the
        # stale 2026-01-01 date.
        assert date.fromisoformat(r3.json()["next_run_date"]) >= date.today()
    finally:
        await client.aclose()
