"""User-configured SMTP accounts. datamodel.md §4, edgecases.md §8.
Mirrors identity/profile_service.py's payment_instruction CRUD exactly
-- another per-tenant table of encrypted third-party credentials.
"""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.security import decrypt_fields, encrypt_fields, mask_fields
from tallyquo.notifications import smtp_client

_COLUMNS = (
    "id, label, from_name, from_address, smtp_host, smtp_port, smtp_security, "
    "smtp_username, is_default, verified_at, created_at"
)


async def list_accounts(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        text(
            f"SELECT {_COLUMNS} FROM email_account "
            "WHERE archived_at IS NULL ORDER BY is_default DESC, label"
        )
    )
    return [dict(r) for r in result.mappings().all()]


async def create_account(session: AsyncSession, tenant_id: UUID, data: dict) -> dict:
    account_id = uuid4()
    password = data.pop("password")
    if data.get("is_default"):
        await session.execute(
            text("UPDATE email_account SET is_default = false WHERE tenant_id = :t AND is_default = true"),
            {"t": tenant_id},
        )
    await session.execute(
        text(
            "INSERT INTO email_account "
            "(id, tenant_id, label, from_name, from_address, smtp_host, smtp_port, "
            " smtp_security, smtp_username, credentials_encrypted, is_default) "
            "VALUES (:id, :tenant_id, :label, :from_name, :from_address, :smtp_host, "
            " :smtp_port, :smtp_security, :smtp_username, :credentials_encrypted, :is_default)"
        ),
        {
            "id": account_id,
            "tenant_id": tenant_id,
            "credentials_encrypted": encrypt_fields({"password": password}),
            **data,
        },
    )
    return await get_account(session, account_id)  # type: ignore[return-value]


async def get_account(session: AsyncSession, account_id: UUID) -> dict | None:
    result = await session.execute(
        text(f"SELECT {_COLUMNS} FROM email_account WHERE id = :id AND archived_at IS NULL"),
        {"id": account_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def archive_account(session: AsyncSession, account_id: UUID) -> bool:
    result = await session.execute(
        text("UPDATE email_account SET archived_at = now() WHERE id = :id AND archived_at IS NULL"),
        {"id": account_id},
    )
    return result.rowcount > 0


async def get_default_account_id(session: AsyncSession) -> UUID | None:
    result = await session.execute(
        text(
            "SELECT id FROM email_account "
            "WHERE archived_at IS NULL ORDER BY is_default DESC, created_at LIMIT 1"
        )
    )
    row = result.first()
    return row[0] if row else None


async def load_smtp_config(session: AsyncSession, account_id: UUID) -> smtp_client.SmtpConfig | None:
    result = await session.execute(
        text(
            "SELECT from_name, from_address, smtp_host, smtp_port, smtp_security, "
            "smtp_username, credentials_encrypted FROM email_account "
            "WHERE id = :id AND archived_at IS NULL"
        ),
        {"id": account_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    password = decrypt_fields(row["credentials_encrypted"])["password"]
    return smtp_client.SmtpConfig(
        host=row["smtp_host"],
        port=row["smtp_port"],
        security=row["smtp_security"],
        username=row["smtp_username"],
        password=password,
        from_name=row["from_name"],
        from_address=row["from_address"],
    )


class AccountNotFound(Exception):
    pass


async def verify_account(session: AsyncSession, account_id: UUID) -> None:
    """O-adjacent: a test connect-and-authenticate, no message sent.
    Raises smtp_client.SmtpSendFailed on failure -- callers surface that
    message directly, it's already user-facing."""
    config = await load_smtp_config(session, account_id)
    if config is None:
        raise AccountNotFound
    await smtp_client.verify(config)
    await session.execute(
        text("UPDATE email_account SET verified_at = now() WHERE id = :id"), {"id": account_id}
    )
