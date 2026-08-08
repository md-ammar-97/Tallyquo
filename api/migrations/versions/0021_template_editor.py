"""Phase 4 workstream 4.2: the actual template editor. Two real,
previously-undiscovered gaps found while starting this:

1. `template.theme.font_scale` has existed in every system template's
   JSONB since migration 0006 (`{"accent_color": ..., "font_scale": 1.0}`)
   but `pdf_renderer.py` never read it -- every PDF used the same fixed
   font sizes regardless. `logo_position`/`margins_mm` didn't exist at
   all; adding them here with defaults matching the current hardcoded
   renderer behaviour (top_left, 20mm) so existing templates render
   identically until a tenant actually changes them.

2. `business_profile.logo_ref`/`logo_dark_ref` have existed since
   migration 0002 (Phase 1's 1.5, "Logo upload") but no upload endpoint
   was ever built -- confirmed by grepping the whole codebase for any
   write to either column. A "logo position" control in the editor
   would be inert without something to position, so this migration
   doesn't touch it (no schema change needed, the columns are already
   right), but `identity/profile_router.py`'s new upload endpoint in
   this same commit closes it.

`template_version_history` (datamodel.md, spec'd since migration 0006
but never built -- "there is no template editor yet (4.2)") is added
now because there is one. Editing a tenant-owned template bumps
`template.version` and archives the *previous* theme/blocks here
first; `render_pdf` for an issued invoice checks this table before
falling back to the current `template` row, so an edit can never
change how an already-issued invoice re-renders (X4/L14) -- a real gap
that existed until this migration, since the old render_pdf query
looked up `template_id` alone with no version filter at all.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE template
        SET theme = theme || '{"logo_position": "top_left", "margins_mm": 20}'::jsonb
        WHERE NOT (theme ? 'logo_position')
        """
    )

    op.execute(
        """
        CREATE TABLE template_version_history (
          template_id   uuid NOT NULL REFERENCES template(id),
          tenant_id     uuid,
          version       integer NOT NULL,
          theme         jsonb NOT NULL,
          blocks        jsonb NOT NULL,
          created_at    timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (template_id, version)
        )
        """
    )
    op.execute("ALTER TABLE template_version_history ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE template_version_history FORCE ROW LEVEL SECURITY")
    # Same hybrid policy as `template` itself (0019): a system template's
    # history (tenant_id NULL) is visible to everyone; a tenant-owned
    # template's history only to its own tenant.
    op.execute(
        """
        CREATE POLICY tenant_isolation ON template_version_history
          USING      (tenant_id IS NULL OR tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    # Append-only, same discipline as audit_log: a row is written once,
    # when superseded by the next edit, and never touched again.
    op.execute("GRANT SELECT, INSERT ON template_version_history TO tallyquo_app")
    op.execute("REVOKE UPDATE, DELETE ON template_version_history FROM tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS template_version_history")
    op.execute(
        """
        UPDATE template
        SET theme = theme - 'logo_position' - 'margins_mm'
        """
    )
