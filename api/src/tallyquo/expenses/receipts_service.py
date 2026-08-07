"""Receipt upload: storage + OCR + dedup. edgecases.md E1, E3-E5, E13.

E4 (multi-page PDF): all pages are retained via storage.upload as-is,
but OCR only runs against image uploads here -- rasterizing PDF page 1
would need a PDF-rendering system library (poppler/pdf2image or
PyMuPDF), the same category of dependency that ruled out WeasyPrint for
PDF *generation* in Phase 1 (unavailable on Render's standard Python
buildpack). A PDF receipt still uploads and stores fine; it just falls
straight to manual entry, which E3 already establishes as an
acceptable, undramatic path.
"""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core import storage
from tallyquo.expenses import ocr

_OCR_ELIGIBLE_MIMES = {"image/png", "image/jpeg", "image/gif"}


async def upload_receipt(session: AsyncSession, tenant_id: UUID, data: bytes) -> dict:
    file_hash = bytes.fromhex(storage.content_hash(data))

    existing = (
        await session.execute(
            text(
                "SELECT id, expense_id, file_ref, mime_type FROM receipt "
                "WHERE tenant_id = :t AND file_hash = :h"
            ),
            {"t": tenant_id, "h": file_hash},
        )
    ).mappings().first()
    if existing is not None:
        # E5: deduplicated by content hash -- told it already exists rather
        # than silently stored twice.
        return {**dict(existing), "already_existed": True, "ocr": None}

    key, mime = storage.upload(str(tenant_id), ["receipts", str(uuid4())], data)

    ocr_result = None
    if mime in _OCR_ELIGIBLE_MIMES:
        ocr_result = await ocr.extract_receipt_fields(data, mime)

    receipt_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO receipt (id, tenant_id, file_ref, file_hash, mime_type, byte_size) "
            "VALUES (:id, :tenant_id, :file_ref, :file_hash, :mime_type, :byte_size)"
        ),
        {
            "id": receipt_id,
            "tenant_id": tenant_id,
            "file_ref": key,
            "file_hash": file_hash,
            "mime_type": mime,
            "byte_size": len(data),
        },
    )
    return {
        "id": receipt_id,
        "expense_id": None,
        "file_ref": key,
        "mime_type": mime,
        "already_existed": False,
        "ocr": ocr_result,
    }


async def unprocessed_receipts(session: AsyncSession) -> list[dict]:
    # E1: orphan receipts (uploaded, no expense attached yet) are retained
    # and listed, never silently discarded.
    result = await session.execute(
        text(
            "SELECT id, file_ref, mime_type, byte_size, uploaded_at FROM receipt "
            "WHERE expense_id IS NULL ORDER BY uploaded_at DESC"
        )
    )
    return [dict(r) for r in result.mappings().all()]


async def signed_receipt_url(session: AsyncSession, receipt_id: UUID) -> str | None:
    row = (
        await session.execute(text("SELECT file_ref FROM receipt WHERE id = :id"), {"id": receipt_id})
    ).mappings().first()
    if row is None:
        return None
    return storage.signed_url(row["file_ref"])
