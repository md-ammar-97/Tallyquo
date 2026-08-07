"""Clients: datamodel.md §5. tax_treatment is the field that makes
per-client tax correctness possible (problem-statement.md §6.3)."""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_COLUMNS = (
    "id, legal_name, display_name, contact_name, email, phone, "
    "address_line1, address_line2, city, region_code, postal_code, country_code, "
    "tax_treatment, is_gst_registered, treatment_override_reason, "
    "default_currency, default_payment_terms_days, default_rate, notes, "
    "created_at, archived_at"
)


async def list_clients(session: AsyncSession, include_archived: bool = False) -> list[dict]:
    where = "" if include_archived else "WHERE archived_at IS NULL"
    result = await session.execute(
        text(f"SELECT {_COLUMNS} FROM client {where} ORDER BY legal_name")
    )
    return [dict(row) for row in result.mappings().all()]


async def get_client(session: AsyncSession, client_id: UUID) -> dict | None:
    result = await session.execute(
        text(f"SELECT {_COLUMNS} FROM client WHERE id = :id"), {"id": client_id}
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def create_client(session: AsyncSession, tenant_id: UUID, data: dict) -> dict:
    # RLS's WITH CHECK validates tenant_id matches the session context, but
    # doesn't fill it in -- every INSERT sets it explicitly.
    client_id = uuid4()
    columns = [*data.keys(), "id", "tenant_id"]
    placeholders = ", ".join(f":{c}" for c in columns)
    await session.execute(
        text(f"INSERT INTO client ({', '.join(columns)}) VALUES ({placeholders})"),
        {**data, "id": client_id, "tenant_id": tenant_id},
    )
    return await get_client(session, client_id)  # type: ignore[return-value]


async def update_client(session: AsyncSession, client_id: UUID, data: dict) -> dict | None:
    if not data:
        return await get_client(session, client_id)
    set_clause = ", ".join(f"{c} = :{c}" for c in data)
    result = await session.execute(
        text(f"UPDATE client SET {set_clause} WHERE id = :id"),
        {**data, "id": client_id},
    )
    if result.rowcount == 0:
        return None
    return await get_client(session, client_id)


async def archive_client(session: AsyncSession, client_id: UUID) -> bool:
    result = await session.execute(
        text("UPDATE client SET archived_at = now() WHERE id = :id AND archived_at IS NULL"),
        {"id": client_id},
    )
    return result.rowcount > 0


async def add_evidence(session: AsyncSession, tenant_id: UUID, client_id: UUID, data: dict) -> dict:
    evidence_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO client_evidence "
            "(id, tenant_id, client_id, kind, file_ref, file_hash, effective_date, expires_at, note) "
            "VALUES (:id, :tenant_id, :client_id, :kind, :file_ref, :file_hash, :effective_date, "
            " :expires_at, :note)"
        ),
        {"id": evidence_id, "tenant_id": tenant_id, "client_id": client_id, **data},
    )
    result = await session.execute(
        text(
            "SELECT id, kind, file_ref, effective_date, expires_at, uploaded_at "
            "FROM client_evidence WHERE id = :id"
        ),
        {"id": evidence_id},
    )
    return dict(result.mappings().one())


async def list_evidence(session: AsyncSession, client_id: UUID) -> list[dict]:
    result = await session.execute(
        text(
            "SELECT id, kind, file_ref, effective_date, expires_at, uploaded_at "
            "FROM client_evidence WHERE client_id = :client_id ORDER BY uploaded_at DESC"
        ),
        {"client_id": client_id},
    )
    return [dict(row) for row in result.mappings().all()]
