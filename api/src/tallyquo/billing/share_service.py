"""Public shareable invoice links. implementation_plan.md 2.12-2.13,
reframed per direct user instruction: no email sending, no
sender-domain verification -- download, on-platform view, and a
shareable public link are the whole feature.

Same bootstrap-lookup pattern as identity's email_tenant_lookup /
session_token_lookup: a public request has a token but no tenant
context yet, and `invoice` is RLS-FORCEd, so resolution happens through
`invoice_share_lookup`, which has no RLS of its own.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.db import raw_session
from tallyquo.core.security import generate_opaque_token, hash_opaque_token


class InvoiceNotShareable(Exception):
    """Drafts can't be shared -- nothing final to show yet."""


async def get_or_create_share_link(session: AsyncSession, tenant_id: UUID, invoice_id: UUID) -> str | None:
    row = (
        await session.execute(
            text("SELECT share_token, status FROM invoice WHERE id = :id"), {"id": invoice_id}
        )
    ).mappings().first()
    if row is None:
        return None
    if row["status"] == "draft":
        raise InvoiceNotShareable("Issue this invoice before sharing it.")
    if row["share_token"] is not None:
        return row["share_token"]

    token = generate_opaque_token()
    await session.execute(
        text("UPDATE invoice SET share_token = :token WHERE id = :id"),
        {"token": token, "id": invoice_id},
    )
    await session.execute(
        text(
            "INSERT INTO invoice_share_lookup (token_hash, tenant_id, invoice_id) "
            "VALUES (:token_hash, :tenant_id, :invoice_id)"
        ),
        {"token_hash": hash_opaque_token(token), "tenant_id": tenant_id, "invoice_id": invoice_id},
    )
    return token


async def revoke_share_link(session: AsyncSession, invoice_id: UUID) -> bool:
    row = (
        await session.execute(text("SELECT share_token FROM invoice WHERE id = :id"), {"id": invoice_id})
    ).mappings().first()
    if row is None or row["share_token"] is None:
        return False
    await session.execute(
        text("DELETE FROM invoice_share_lookup WHERE token_hash = :h"),
        {"h": hash_opaque_token(row["share_token"])},
    )
    await session.execute(text("UPDATE invoice SET share_token = NULL WHERE id = :id"), {"id": invoice_id})
    return True


async def resolve_share_token(token: str) -> tuple[UUID, UUID] | None:
    """Public entry point -- no tenant context yet, mirrors the auth
    bootstrap lookups exactly (architecture.md §5)."""
    async with raw_session() as session:
        row = (
            await session.execute(
                text("SELECT tenant_id, invoice_id FROM invoice_share_lookup WHERE token_hash = :h"),
                {"h": hash_opaque_token(token)},
            )
        ).mappings().first()
    if row is None:
        return None
    return row["tenant_id"], row["invoice_id"]
