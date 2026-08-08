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

    theme = package.get("theme")
    if not isinstance(theme, dict):
        raise InvalidTemplatePackage("Package theme must be an object.")
    accent = theme.get("accent_color")
    if not isinstance(accent, str) or not accent.startswith("#") or len(accent) not in (4, 7):
        raise InvalidTemplatePackage("Package theme.accent_color must be a hex colour, e.g. \"#0D99FF\".")
    font_scale = theme.get("font_scale", 1.0)
    if not isinstance(font_scale, (int, float, Decimal)) or font_scale <= 0:
        raise InvalidTemplatePackage("Package theme.font_scale must be a positive number.")

    blocks = package.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise InvalidTemplatePackage("Package blocks must be a non-empty list.")
    unknown = set(blocks) - _KNOWN_BLOCKS
    if unknown:
        raise InvalidTemplatePackage(f"Package references unknown block type(s): {sorted(unknown)}.")
    missing = _REQUIRED_BLOCKS - set(blocks)
    if missing:
        # M2, P1: the whole point -- reject rather than import a template
        # that would (once 4.2 makes blocks render-affecting) silently
        # drop compliance-critical content from a real invoice.
        raise InvalidTemplatePackage(
            f"Package is missing required compliance block(s): {sorted(missing)}. "
            "A template can't omit these."
        )


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
