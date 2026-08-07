"""OTP auth business logic. architecture.md §5 is the spec this implements
line for line -- see the docstring on each function for which edge case
(edgecases.md §1) it exists to satisfy.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.config import get_settings
from tallyquo.core.db import raw_session
from tallyquo.core.security import (
    codes_match,
    create_access_token,
    generate_opaque_token,
    generate_otp_code,
    hash_ip,
    hash_opaque_token,
    hash_otp_code,
    normalize_otp_input,
)
from tallyquo.core.tenant_context import tenant_session


class OtpInvalid(Exception):
    pass


class OtpExpired(Exception):
    pass


class RefreshTokenInvalid(Exception):
    pass


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str


async def request_otp(email: str, ip: str | None) -> str | None:
    """edgecases.md A1 (no enumeration), A2 (rate limits, no limit leaked).

    The HTTP router always returns the same response regardless of this
    function's return value -- callers there must discard it. It returns
    the plaintext code (or None if suppressed by a rate limit) purely so
    tests can call this directly instead of scraping logs; production's
    only consumer of the code itself is the notifications module (Phase 2,
    not built yet -- logged in non-production environments in the meantime
    as a stopgap for manual testing).
    """
    settings = get_settings()
    email = email.strip().lower()
    ip_hash = hash_ip(ip)

    async with raw_session() as session:
        async with session.begin():
            email_count = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM otp_code WHERE email = :email "
                        "AND created_at > :since"
                    ),
                    {
                        "email": email,
                        "since": datetime.now(UTC)
                        - timedelta(seconds=settings.otp_requests_per_email_window_seconds),
                    },
                )
            ).scalar_one()
            if email_count >= settings.otp_requests_per_email_window:
                return None  # rate-limited -- silently no-op, response is identical either way

            if ip_hash is not None:
                ip_count = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM otp_code WHERE ip_hash = :ip_hash "
                            "AND created_at > :since"
                        ),
                        {
                            "ip_hash": ip_hash,
                            "since": datetime.now(UTC)
                            - timedelta(seconds=settings.otp_requests_per_ip_window_seconds),
                        },
                    )
                ).scalar_one()
                if ip_count >= settings.otp_requests_per_ip_window:
                    return None

            # A2: latest code invalidates prior ones.
            await session.execute(
                text(
                    "UPDATE otp_code SET consumed_at = now() "
                    "WHERE email = :email AND consumed_at IS NULL"
                ),
                {"email": email},
            )

            code = generate_otp_code()
            await session.execute(
                text(
                    "INSERT INTO otp_code (email, code_hash, expires_at, ip_hash) "
                    "VALUES (:email, :code_hash, :expires_at, :ip_hash)"
                ),
                {
                    "email": email,
                    "code_hash": hash_otp_code(email, code),
                    "expires_at": datetime.now(UTC)
                    + timedelta(seconds=settings.otp_ttl_seconds),
                    "ip_hash": ip_hash,
                },
            )

    # TODO(Phase 1, notifications module): send `code` by email.
    if get_settings().environment != "production":
        from tallyquo.core.logging import get_logger

        get_logger(__name__).info("otp_code_issued_dev_only", email=email, code=code)

    return code


async def _find_tenant_id(session: AsyncSession, email: str) -> UUID | None:
    result = await session.execute(
        text("SELECT tenant_id FROM email_tenant_lookup WHERE email = :email"),
        {"email": email},
    )
    row = result.first()
    return row[0] if row else None


async def verify_otp(email: str, raw_code: str, device_label: str | None, ip: str | None) -> TokenPair:
    """edgecases.md A3 (expiry), A8 (single-use), A9 (attempt cap).
    Signup and login are the same flow -- first success for an unknown
    email provisions the tenant (architecture.md §5).
    """
    settings = get_settings()
    email = email.strip().lower()
    code = normalize_otp_input(raw_code)

    # Any write made in this block must commit regardless of outcome (in
    # particular, the failed-attempt counter) -- raising from *inside* a
    # `session.begin()` block rolls the whole transaction back, silently
    # undoing those writes. So: capture the outcome, let the block exit
    # normally every time, and raise afterward if it failed. (This bit us
    # for real during Phase 1 dev: the attempt counter and the token-family
    # revoke-on-replay below were both being rolled back before this fix.)
    error: OtpExpired | OtpInvalid | None = None
    tenant_id: UUID | None = None

    async with raw_session() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    "SELECT id, code_hash, expires_at, attempts FROM otp_code "
                    "WHERE email = :email AND consumed_at IS NULL "
                    "ORDER BY created_at DESC LIMIT 1 FOR UPDATE"
                ),
                {"email": email},
            )
            row = result.first()
            if row is None:
                error = OtpExpired("Code expired. Request a new one.")
            else:
                otp_id, code_hash, expires_at, attempts = row
                expires_at = (
                    expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at
                )
                if expires_at < datetime.now(UTC):
                    error = OtpExpired("Code expired. Request a new one.")
                elif not codes_match(hash_otp_code(email, code), bytes(code_hash)):
                    new_attempts = attempts + 1
                    if new_attempts >= settings.otp_max_attempts:
                        await session.execute(
                            text(
                                "UPDATE otp_code SET attempts = :a, consumed_at = now() "
                                "WHERE id = :id"
                            ),
                            {"a": new_attempts, "id": otp_id},
                        )
                    else:
                        await session.execute(
                            text("UPDATE otp_code SET attempts = :a WHERE id = :id"),
                            {"a": new_attempts, "id": otp_id},
                        )
                    remaining = max(settings.otp_max_attempts - new_attempts, 0)
                    error = OtpInvalid(f"That code didn't match. You have {remaining} attempts left.")
                else:
                    await session.execute(
                        text("UPDATE otp_code SET consumed_at = now() WHERE id = :id"),
                        {"id": otp_id},
                    )
                    tenant_id = await _find_tenant_id(session, email)

    if error is not None:
        raise error

    is_new_tenant = tenant_id is None
    if is_new_tenant:
        tenant_id = uuid4()
        user_id = uuid4()
        async with tenant_session(tenant_id) as session:
            await session.execute(text("INSERT INTO tenant (id) VALUES (:id)"), {"id": tenant_id})
            await session.execute(
                text(
                    "INSERT INTO app_user (id, tenant_id, email, email_verified_at) "
                    "VALUES (:id, :tenant_id, :email, now())"
                ),
                {"id": user_id, "tenant_id": tenant_id, "email": email},
            )
            await session.execute(
                text(
                    "INSERT INTO email_tenant_lookup (email, tenant_id, user_id) "
                    "VALUES (:email, :tenant_id, :user_id)"
                ),
                {"email": email, "tenant_id": tenant_id, "user_id": user_id},
            )
    else:
        async with tenant_session(tenant_id) as session:
            result = await session.execute(
                text("SELECT id FROM app_user WHERE tenant_id = :tenant_id AND email = :email"),
                {"tenant_id": tenant_id, "email": email},
            )
            user_id = result.scalar_one()
            await session.execute(
                text("UPDATE app_user SET last_seen_at = now() WHERE id = :id"),
                {"id": user_id},
            )

    return await _create_session(tenant_id, user_id, device_label, ip, token_family=uuid4())


async def _create_session(
    tenant_id: UUID, user_id: UUID, device_label: str | None, ip: str | None, token_family: UUID
) -> TokenPair:
    settings = get_settings()
    session_id = uuid4()
    refresh_token = generate_opaque_token()
    async with tenant_session(tenant_id, actor_id=user_id) as session:
        await session.execute(
            text(
                "INSERT INTO session "
                "(id, tenant_id, user_id, refresh_token_hash, token_family, "
                " device_label, ip_hash, expires_at) "
                "VALUES (:id, :tenant_id, :user_id, :hash, :family, :label, :ip_hash, :expires_at)"
            ),
            {
                "id": session_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "hash": hash_opaque_token(refresh_token),
                "family": token_family,
                "label": device_label,
                "ip_hash": hash_ip(ip),
                "expires_at": datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
            },
        )
    # Non-RLS companion index -- see migrations/0002 for why this needs to
    # exist alongside the RLS-protected `session` row.
    async with raw_session() as lookup_session:
        async with lookup_session.begin():
            await lookup_session.execute(
                text(
                    "INSERT INTO session_token_lookup (token_hash, tenant_id, session_id) "
                    "VALUES (:hash, :tenant_id, :session_id)"
                ),
                {
                    "hash": hash_opaque_token(refresh_token),
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                },
            )
    access_token = create_access_token(tenant_id=tenant_id, user_id=user_id, session_id=session_id)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


async def refresh_session(refresh_token: str, ip: str | None) -> TokenPair:
    """edgecases.md A11: rotate on every use; a replayed (already-rotated)
    token revokes the entire token family, not just itself."""
    token_hash = hash_opaque_token(refresh_token)

    # Bootstrap step: discover the tenant via the non-RLS lookup, exactly
    # like verify_otp discovers it via email_tenant_lookup.
    async with raw_session() as lookup_session:
        result = await lookup_session.execute(
            text("SELECT tenant_id, session_id FROM session_token_lookup WHERE token_hash = :hash"),
            {"hash": token_hash},
        )
        row = result.first()
        if row is None:
            raise RefreshTokenInvalid("Invalid refresh token.")
        tenant_id, session_id = row

    # Same "write must survive regardless of outcome" concern as verify_otp
    # above -- the family-wide revoke below must commit even though this
    # call ultimately raises.
    error: RefreshTokenInvalid | None = None
    user_id: UUID | None = None
    token_family: UUID | None = None

    # Authoritative step: RLS-scoped read/write against the real session row.
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(
                "SELECT user_id, token_family, revoked_at, expires_at "
                "FROM session WHERE id = :id"
            ),
            {"id": session_id},
        )
        row = result.first()
        if row is None:
            error = RefreshTokenInvalid("Invalid refresh token.")
        else:
            user_id, token_family, revoked_at, expires_at = row

            if revoked_at is not None:
                # Replay of an already-rotated (or already-logged-out)
                # token. Revoke the whole family -- architecture.md §5.
                await session.execute(
                    text(
                        "UPDATE session SET revoked_at = now() "
                        "WHERE token_family = :family AND revoked_at IS NULL"
                    ),
                    {"family": token_family},
                )
                error = RefreshTokenInvalid("This session was revoked. Please sign in again.")
            else:
                expires_at = (
                    expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at
                )
                if expires_at < datetime.now(UTC):
                    error = RefreshTokenInvalid("Session expired. Please sign in again.")
                else:
                    await session.execute(
                        text("UPDATE session SET revoked_at = now() WHERE id = :id"),
                        {"id": session_id},
                    )

    if error is not None:
        raise error

    return await _create_session(tenant_id, user_id, device_label=None, ip=ip, token_family=token_family)


async def logout(tenant_id: UUID, session_id: UUID) -> None:
    async with tenant_session(tenant_id) as session:
        await session.execute(
            text("UPDATE session SET revoked_at = now() WHERE id = :id AND revoked_at IS NULL"),
            {"id": session_id},
        )


async def list_sessions(tenant_id: UUID, user_id: UUID) -> list[dict]:
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(
                "SELECT id, device_label, created_at, last_used_at, expires_at "
                "FROM session WHERE user_id = :user_id AND revoked_at IS NULL "
                "AND expires_at > now() ORDER BY created_at DESC"
            ),
            {"user_id": user_id},
        )
        return [dict(row._mapping) for row in result.all()]


async def revoke_session(tenant_id: UUID, user_id: UUID, session_id: UUID) -> bool:
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(
                "UPDATE session SET revoked_at = now() "
                "WHERE id = :id AND user_id = :user_id AND revoked_at IS NULL"
            ),
            {"id": session_id, "user_id": user_id},
        )
        return result.rowcount > 0
