"""Business profile + payment instructions. datamodel.md §4.

registration_status is a state machine (not_registered -> pending ->
registered) whose `registration_effective_date` drives automatic tax
behaviour on invoices (problem-statement.md §6.2) -- everything downstream
reads that date, never today's date or a manual toggle.
"""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.security import decrypt_fields, encrypt_fields, mask_fields

_PROFILE_COLUMNS = (
    "legal_name, operating_name, address_line1, address_line2, city, "
    "region_code, postal_code, country_code, email, phone, website, "
    "default_currency, default_payment_terms_days, invoice_number_format, "
    "invoice_number_prefix, fiscal_year_start_month, timezone, "
    "registration_status, gst_hst_number, registration_effective_date, "
    "logo_ref, logo_dark_ref, default_template_id, created_at, updated_at, tenant_id"
)


async def get_profile(session: AsyncSession, tenant_id: UUID) -> dict | None:
    result = await session.execute(
        text(f"SELECT {_PROFILE_COLUMNS} FROM business_profile WHERE tenant_id = :t"),
        {"t": tenant_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def upsert_profile(session: AsyncSession, tenant_id: UUID, data: dict) -> dict:
    existing = await get_profile(session, tenant_id)
    params = {**data, "tenant_id": tenant_id}
    if existing is None:
        columns = [*data.keys(), "tenant_id"]
        placeholders = ", ".join(f":{c}" for c in columns)
        await session.execute(
            text(
                f"INSERT INTO business_profile ({', '.join(columns)}) "
                f"VALUES ({placeholders})"
            ),
            params,
        )
    else:
        set_clause = ", ".join(f"{c} = :{c}" for c in data)
        await session.execute(
            text(
                f"UPDATE business_profile SET {set_clause}, updated_at = now() "
                "WHERE tenant_id = :tenant_id"
            ),
            params,
        )
    return await get_profile(session, tenant_id)  # type: ignore[return-value]


async def update_registration(session: AsyncSession, tenant_id: UUID, data: dict) -> dict:
    return await upsert_profile(session, tenant_id, data)


async def list_payment_instructions(session: AsyncSession, tenant_id: UUID) -> list[dict]:
    result = await session.execute(
        text(
            "SELECT id, label, method, provider, account_holder, currency, "
            "is_default, fields_encrypted FROM payment_instruction "
            "WHERE tenant_id = :t AND archived_at IS NULL ORDER BY is_default DESC, label"
        ),
        {"t": tenant_id},
    )
    rows = []
    for row in result.mappings().all():
        row = dict(row)
        blob = row.pop("fields_encrypted")
        row["fields_masked"] = mask_fields(decrypt_fields(blob)) if blob else {}
        rows.append(row)
    return rows


async def create_payment_instruction(session: AsyncSession, tenant_id: UUID, data: dict) -> dict:
    instruction_id = uuid4()
    fields = data.pop("fields", {})
    if data.get("is_default"):
        await session.execute(
            text(
                "UPDATE payment_instruction SET is_default = false "
                "WHERE tenant_id = :t AND is_default = true"
            ),
            {"t": tenant_id},
        )
    await session.execute(
        text(
            "INSERT INTO payment_instruction "
            "(id, tenant_id, label, method, provider, account_holder, currency, "
            " fields_encrypted, is_default) "
            "VALUES (:id, :tenant_id, :label, :method, :provider, :account_holder, "
            " :currency, :fields_encrypted, :is_default)"
        ),
        {
            "id": instruction_id,
            "tenant_id": tenant_id,
            "fields_encrypted": encrypt_fields(fields),
            **data,
        },
    )
    return {
        "id": instruction_id,
        "fields_masked": mask_fields(fields),
        **data,
    }


async def reveal_payment_instruction(session: AsyncSession, tenant_id: UUID, instruction_id: UUID) -> dict | None:
    result = await session.execute(
        text(
            "SELECT id, label, method, fields_encrypted FROM payment_instruction "
            "WHERE tenant_id = :t AND id = :id AND archived_at IS NULL"
        ),
        {"t": tenant_id, "id": instruction_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    blob = row["fields_encrypted"]
    return {
        "id": row["id"],
        "label": row["label"],
        "method": row["method"],
        "fields": decrypt_fields(blob) if blob else {},
    }


async def archive_payment_instruction(session: AsyncSession, tenant_id: UUID, instruction_id: UUID) -> bool:
    result = await session.execute(
        text(
            "UPDATE payment_instruction SET archived_at = now() "
            "WHERE tenant_id = :t AND id = :id AND archived_at IS NULL"
        ),
        {"t": tenant_id, "id": instruction_id},
    )
    return result.rowcount > 0
