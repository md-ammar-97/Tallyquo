"""Template selection, and the portable .json package format (Phase 4,
implementation_plan.md 4.1). Depends on Phase 1's 1.19 -- which, in the
codebase as it actually stands, shipped narrower than its own row
describes: `template.blocks` is stored but pdf_renderer.py doesn't
read it (rendering is a fixed layout; only `theme.accent_color` is
actually applied). That's still true after this module -- block-driven
layout (show/hide/reorder) is 4.2's full custom-builder scope, not
reopened here. What *was* a real, unmarked gap and is fixed by this
module: there was no way for a tenant to choose a template at all
(`invoice.template_id` was always pinned to the system default,
regardless of any preference), so a template's theme could never
actually reach a rendered PDF. See invoices_service.py's template-pin
and render_pdf changes in this same commit.

Compliance-safety (M1/M2, P1): `blocks` doesn't drive rendering yet, so
there is no live risk of an imported package silently hiding the
compliance-critical fields from a real PDF. Import validation still
requires the compliance-critical block names to be present in the
imported `blocks` array regardless -- so a package is only ever
IMPORTED in the state that would already be renderer-safe once 4.2
makes `blocks` real, rather than storing something that becomes
unsafe the moment that dependency ships.
"""

import json
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PACKAGE_SCHEMA_VERSION = 1

# Compliance-critical: party identification, dates/number, line items,
# and the tax/total breakdown -- everything a legally valid invoice needs.
# "payment" (instructions) and "footer" are the only genuinely optional
# blocks in the current vocabulary.
_REQUIRED_BLOCKS = {"supplier", "document", "bill_to", "services", "totals"}
_KNOWN_BLOCKS = _REQUIRED_BLOCKS | {"payment", "footer"}

_COLUMNS = "id, name, schema_version, version, theme, blocks, is_system, is_default, tenant_id"


class TemplateError(Exception):
    pass


class TemplateNotFound(TemplateError):
    pass


class InvalidTemplatePackage(TemplateError):
    """M1/P1: rejects the whole import rather than partially applying a
    malformed or unsafe package."""


async def list_templates(session: AsyncSession) -> list[dict]:
    # RLS (migration 0019) already limits this to system rows (tenant_id
    # IS NULL) plus the caller's own -- no tenant_id filter needed here,
    # same convention as every other RLS-scoped query in this codebase.
    result = await session.execute(
        text(f"SELECT {_COLUMNS} FROM template WHERE archived_at IS NULL ORDER BY is_system DESC, name")
    )
    return [dict(r) for r in result.mappings().all()]


async def get_template(session: AsyncSession, template_id: UUID) -> dict | None:
    result = await session.execute(
        text(f"SELECT {_COLUMNS} FROM template WHERE id = :id AND archived_at IS NULL"),
        {"id": template_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


_LOGO_POSITIONS = {"top_left", "top_center", "top_right", "none"}


def _validate_theme(theme: object) -> None:
    if not isinstance(theme, dict):
        raise InvalidTemplatePackage("theme must be an object.")
    accent = theme.get("accent_color")
    if not isinstance(accent, str) or not accent.startswith("#") or len(accent) not in (4, 7):
        raise InvalidTemplatePackage("theme.accent_color must be a hex colour, e.g. \"#0D99FF\".")
    font_scale = theme.get("font_scale", 1.0)
    if not isinstance(font_scale, (int, float, Decimal)) or not (0.5 <= font_scale <= 1.5):
        raise InvalidTemplatePackage("theme.font_scale must be a number between 0.5 and 1.5.")
    margins_mm = theme.get("margins_mm", 20)
    if not isinstance(margins_mm, (int, float, Decimal)) or not (10 <= margins_mm <= 40):
        raise InvalidTemplatePackage("theme.margins_mm must be a number between 10 and 40.")
    logo_position = theme.get("logo_position", "top_left")
    if logo_position not in _LOGO_POSITIONS:
        raise InvalidTemplatePackage(f"theme.logo_position must be one of {sorted(_LOGO_POSITIONS)}.")


def _validate_blocks(blocks: object) -> None:
    if not isinstance(blocks, list) or not blocks:
        raise InvalidTemplatePackage("blocks must be a non-empty list.")
    unknown = set(blocks) - _KNOWN_BLOCKS
    if unknown:
        raise InvalidTemplatePackage(f"blocks references unknown block type(s): {sorted(unknown)}.")
    missing = _REQUIRED_BLOCKS - set(blocks)
    if missing:
        # M2, P1: the whole point -- reject rather than save a template
        # that would silently drop compliance-critical content from a
        # real invoice. The 5 required blocks' *relative order* among
        # themselves doesn't matter (pdf_renderer.py always renders them
        # in a fixed sequence regardless) -- only that all 5 are present.
        raise InvalidTemplatePackage(
            f"blocks is missing required compliance block(s): {sorted(missing)}. "
            "A template can't omit these."
        )


def _validate_package(package: dict) -> None:
    if package.get("package_schema_version") != PACKAGE_SCHEMA_VERSION:
        # X13's sibling: never guess how to interpret an unknown/future
        # package version -- reject outright.
        raise InvalidTemplatePackage(
            f"Unsupported package_schema_version {package.get('package_schema_version')!r} "
            f"(this build understands {PACKAGE_SCHEMA_VERSION})."
        )
    name = package.get("name")
    if not isinstance(name, str) or not name.strip():
        raise InvalidTemplatePackage("Package is missing a template name.")
    _validate_theme(package.get("theme"))
    _validate_blocks(package.get("blocks"))


def export_template(template: dict) -> dict:
    return {
        "package_schema_version": PACKAGE_SCHEMA_VERSION,
        "name": template["name"],
        "theme": template["theme"],
        "blocks": template["blocks"],
    }


async def import_template(session: AsyncSession, tenant_id: UUID, package: dict) -> dict:
    _validate_package(package)
    template_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO template (id, tenant_id, name, schema_version, version, theme, blocks, "
            "is_system, is_default) "
            "VALUES (:id, :tenant_id, :name, 1, 1, :theme, :blocks, false, false)"
        ),
        {
            "id": template_id,
            "tenant_id": tenant_id,
            "name": package["name"],
            "theme": json.dumps(package["theme"]),
            "blocks": json.dumps(package["blocks"]),
        },
    )
    return await get_template(session, template_id)


async def set_default_template(session: AsyncSession, tenant_id: UUID, template_id: UUID) -> None:
    if await get_template(session, template_id) is None:
        # RLS means this is also what happens if the id belongs to
        # another tenant's private template -- indistinguishable from
        # "doesn't exist" (edgecases.md T1: 404, never 403).
        raise TemplateNotFound("Template not found.")
    await session.execute(
        text("UPDATE business_profile SET default_template_id = :id WHERE tenant_id = :t"),
        {"id": template_id, "t": tenant_id},
    )


async def create_template(session: AsyncSession, tenant_id: UUID, name: str, theme: dict, blocks: list) -> dict:
    """4.2: a tenant building a custom template from scratch (or as a
    modified copy of one they can see -- the frontend fetches an
    existing template's theme/blocks and POSTs a changed copy; there is
    no separate server-side clone operation, since it's the same
    request either way)."""
    if not name or not name.strip():
        raise InvalidTemplatePackage("name is required.")
    _validate_theme(theme)
    _validate_blocks(blocks)
    template_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO template (id, tenant_id, name, schema_version, version, theme, blocks, "
            "is_system, is_default) "
            "VALUES (:id, :tenant_id, :name, 1, 1, :theme, :blocks, false, false)"
        ),
        {
            "id": template_id,
            "tenant_id": tenant_id,
            "name": name,
            "theme": json.dumps(theme),
            "blocks": json.dumps(blocks),
        },
    )
    return await get_template(session, template_id)


async def update_template(
    session: AsyncSession, tenant_id: UUID, template_id: UUID, name: str, theme: dict, blocks: list
) -> dict:
    """Editing a template must never change how an already-issued
    invoice re-renders (X4/L14, datamodel.md's template_version_history
    section) -- so before overwriting `template`'s current theme/blocks,
    the CURRENT (about-to-be-superseded) version is frozen into
    `template_version_history` first. `render_pdf` for an issued invoice
    checks that table by (template_id, template_version) before it ever
    looks at the live `template` row."""
    existing = await get_template(session, template_id)
    if existing is None or existing["is_system"] or existing["tenant_id"] != tenant_id:
        # System templates are read-only; RLS would reject the UPDATE at
        # the database level regardless (WITH CHECK requires tenant_id to
        # match), but checking here gives a clean 404 (edgecases.md T1)
        # instead of a raw policy-violation error.
        raise TemplateNotFound("Template not found.")
    if not name or not name.strip():
        raise InvalidTemplatePackage("name is required.")
    _validate_theme(theme)
    _validate_blocks(blocks)

    await session.execute(
        text(
            "INSERT INTO template_version_history (template_id, tenant_id, version, theme, blocks) "
            "VALUES (:id, :tenant_id, :version, :theme, :blocks) "
            "ON CONFLICT (template_id, version) DO NOTHING"
        ),
        {
            "id": template_id,
            "tenant_id": tenant_id,
            "version": existing["version"],
            "theme": json.dumps(existing["theme"]),
            "blocks": json.dumps(existing["blocks"]),
        },
    )
    await session.execute(
        text(
            "UPDATE template SET name = :name, theme = :theme, blocks = :blocks, version = version + 1 "
            "WHERE id = :id"
        ),
        {"id": template_id, "name": name, "theme": json.dumps(theme), "blocks": json.dumps(blocks)},
    )
    return await get_template(session, template_id)


async def archive_template(session: AsyncSession, tenant_id: UUID, template_id: UUID) -> bool:
    existing = await get_template(session, template_id)
    if existing is None or existing["is_system"] or existing["tenant_id"] != tenant_id:
        return False
    await session.execute(text("UPDATE template SET archived_at = now() WHERE id = :id"), {"id": template_id})
    return True


_SAMPLE_LINE_ITEMS = [
    {"description": "Consulting services", "quantity": "10", "unit": "hours", "unit_rate": "100.00", "amount": "1000.00"}
]
_SAMPLE_TAX_LINES = [{"label": "GST/HST — 13%", "rate": "0.13", "amount": "130.00"}]
_SAMPLE_PAYMENT_INSTRUCTION = {
    "currency": "CAD",
    "method": "etransfer",
    "provider": "Sample Bank",
    "account_holder": None,
    "fields": {"email": "you@example.com"},
}


async def render_preview_pdf(session: AsyncSession, tenant_id: UUID, theme: dict, blocks: list) -> bytes:
    """Live preview for the editor (design.md §8.6's "centre: live
    document") -- renders against the tenant's real supplier info and
    logo but canned sample client/line-item data, and is never
    persisted. Lets the editor show real output on every keystroke
    without a save round-trip or a throwaway DB row per change."""
    from tallyquo.core import storage
    from tallyquo.templates.pdf_renderer import render_invoice_pdf

    _validate_theme(theme)
    _validate_blocks(blocks)

    profile_row = (
        await session.execute(
            text(
                "SELECT legal_name, operating_name, address_line1, address_line2, city, "
                "region_code, postal_code, email, gst_hst_number, logo_ref "
                "FROM business_profile WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )
    ).mappings().first()
    supplier = dict(profile_row) if profile_row else {"legal_name": "Your Business Name"}
    logo_bytes = None
    if profile_row and profile_row["logo_ref"]:
        try:
            logo_bytes = storage.download(profile_row["logo_ref"])
        except Exception:  # noqa: BLE001 -- a broken/missing logo must never block preview
            logo_bytes = None

    sample_invoice = {
        "number": "INV-SAMPLE-001",
        "invoice_date": "2026-01-15",
        "due_date": "2026-02-14",
        "currency": "CAD",
        "subtotal": "1000.00",
        "total": "1130.00",
        "notes": "Thank you for your business.",
    }
    sample_client = {
        "legal_name": "Sample Client Inc.",
        "address_line1": "456 Client Ave",
        "city": "Toronto",
        "region_code": "ON",
        "postal_code": "M4B 1B3",
        "country_code": "CA",
    }

    return render_invoice_pdf(
        invoice=sample_invoice,
        supplier=supplier,
        client=sample_client,
        line_items=_SAMPLE_LINE_ITEMS,
        tax_lines=_SAMPLE_TAX_LINES,
        accent_color=theme.get("accent_color", "#0D99FF"),
        font_scale=float(theme.get("font_scale", 1.0)),
        margins_mm=float(theme.get("margins_mm", 20.0)),
        logo_bytes=logo_bytes,
        logo_position=theme.get("logo_position", "top_left"),
        payment_instruction=_SAMPLE_PAYMENT_INSTRUCTION if "payment" in blocks else None,
        notes_visible="footer" in blocks,
        optional_block_order=tuple(blocks),
    )
