"""OTP auth: edgecases.md §1. Uses the app directly over ASGI transport so
these exercise the real router + service + DB, not just the DB layer."""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from tallyquo.core.db import raw_session
from tallyquo.identity import service
from tallyquo.main import app


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _get_code(email: str) -> str:
    # Calls the service directly rather than scraping the HTTP response
    # (which is deliberately identical regardless of outcome, per A1) or
    # log output (unreliable to capture -- depends on logging handler
    # wiring that a test shouldn't need to know about).
    code = await service.request_otp(email, ip=None)
    assert code is not None, "expected a code to be issued, not rate-limited"
    return code


@pytest.mark.asyncio
async def test_request_otp_response_identical_for_any_input():
    """edgecases.md A1: no account enumeration -- known vs unknown email,
    or a rate-limited request, must be indistinguishable."""
    async with await _client() as client:
        r1 = await client.post("/auth/request-otp", json={"email": f"unknown-{uuid4()}@example.com"})
        r2 = await client.post("/auth/request-otp", json={"email": f"unknown-{uuid4()}@example.com"})
        assert r1.status_code == r2.status_code == 200
        assert r1.json() == r2.json()


@pytest.mark.asyncio
async def test_signup_and_login_are_the_same_flow():
    """architecture.md §5: first successful OTP for an unknown email
    provisions the tenant; a second login for the same email must not."""
    email = f"newuser-{uuid4()}@example.com"
    async with await _client() as client:
        code = await _get_code(email)
        r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
        assert r.status_code == 200

        async with raw_session() as session:
            tenant_count_1 = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM email_tenant_lookup WHERE email = :e"
                    ),
                    {"e": email},
                )
            ).scalar_one()
        assert tenant_count_1 == 1

        code2 = await _get_code(email)
        r = await client.post("/auth/verify-otp", json={"email": email, "code": code2})
        assert r.status_code == 200

        async with raw_session() as session:
            tenant_count_2 = (
                await session.execute(
                    text("SELECT count(*) FROM email_tenant_lookup WHERE email = :e"),
                    {"e": email},
                )
            ).scalar_one()
        assert tenant_count_2 == 1, "second login must not provision a second tenant"


@pytest.mark.asyncio
async def test_otp_single_use():
    """edgecases.md A8: the same code cannot be verified twice."""
    email = f"singleuse-{uuid4()}@example.com"
    async with await _client() as client:
        code = await _get_code(email)
        r1 = await client.post("/auth/verify-otp", json={"email": email, "code": code})
        assert r1.status_code == 200
        r2 = await client.post("/auth/verify-otp", json={"email": email, "code": code})
        assert r2.status_code == 401


@pytest.mark.asyncio
async def test_otp_attempt_cap_invalidates_code():
    """edgecases.md A9: 5 attempts, then the code is invalidated even if
    the correct code is later supplied."""
    email = f"attemptcap-{uuid4()}@example.com"
    async with await _client() as client:
        code = await _get_code(email)
        for _ in range(5):
            r = await client.post("/auth/verify-otp", json={"email": email, "code": "000000"})
            assert r.status_code == 401
        r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
        assert r.status_code == 401
        assert "expired" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_pasted_code_with_whitespace_accepted():
    """edgecases.md A4: strip non-digits before comparing."""
    email = f"pasted-{uuid4()}@example.com"
    async with await _client() as client:
        code = await _get_code(email)
        spaced = f"{code[:3]} {code[3:]}"
        r = await client.post("/auth/verify-otp", json={"email": email, "code": spaced})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_gmail_dot_variants_are_distinct_tenants():
    """edgecases.md A6, P1: no provider-specific email normalization."""
    base = uuid4().hex[:8]
    email_a = f"{base}@example.com"
    email_b = f"{base[:4]}.{base[4:]}@example.com"
    async with await _client() as client:
        code_a = await _get_code(email_a)
        await client.post("/auth/verify-otp", json={"email": email_a, "code": code_a})
        code_b = await _get_code(email_b)
        await client.post("/auth/verify-otp", json={"email": email_b, "code": code_b})

        async with raw_session() as session:
            tenants = (
                await session.execute(
                    text(
                        "SELECT tenant_id FROM email_tenant_lookup WHERE email IN (:a, :b)"
                    ),
                    {"a": email_a, "b": email_b},
                )
            ).all()
        assert len({row[0] for row in tenants}) == 2


@pytest.mark.asyncio
async def test_refresh_rotates_and_replay_revokes_family():
    """edgecases.md A11: rotate on every use; replaying an already-rotated
    token revokes every token in the family, including the newest one."""
    email = f"replay-{uuid4()}@example.com"
    async with await _client() as client:
        code = await _get_code(email)
        r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
        first = r.json()

        r = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
        assert r.status_code == 200
        second = r.json()
        assert second["refresh_token"] != first["refresh_token"]

        # Replay the retired token.
        r = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
        assert r.status_code == 401

        # The token issued just before the replay must now be dead too.
        r = await client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_session():
    email = f"logout-{uuid4()}@example.com"
    async with await _client() as client:
        code = await _get_code(email)
        r = await client.post("/auth/verify-otp", json={"email": email, "code": code})
        tokens = r.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        r = await client.post("/auth/logout", headers=headers)
        assert r.status_code == 204

        r = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected():
    async with await _client() as client:
        r = await client.get("/auth/sessions")
        assert r.status_code == 401
