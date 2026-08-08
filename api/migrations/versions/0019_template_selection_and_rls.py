"""Closes a gap found while starting Phase 4 workstream 4.1: `template`
has never had RLS (migration 0006's own comment: "No RLS yet: only
system rows exist in Phase 1, and NULL tenant_id rows must be visible
regardless of session context") -- true until now, since Phase 4 is
where tenant-owned templates (imported or, later, custom-built) start
existing. Also adds `business_profile.default_template_id` so a
tenant can actually choose which template applies to new invoices --
previously there was no selection mechanism at all; every invoice
silently used whichever system template had `is_default = true`.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE business_profile ADD COLUMN default_template_id uuid REFERENCES template(id)"
    )

    op.execute("ALTER TABLE template ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE template FORCE ROW LEVEL SECURITY")
    # Hybrid policy: system rows (tenant_id IS NULL) are visible to every
    # tenant and cannot be claimed as anyone's own; tenant-owned rows are
    # visible and writable only by their own tenant. A tenant can never
    # write a NULL-tenant row -- WITH CHECK requires tenant_id to match
    # the session's own, so "create a fake system template" isn't reachable.
    op.execute(
        """
        CREATE POLICY tenant_isolation ON template
          USING      (tenant_id IS NULL OR tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    # Same default-privileges gotcha as 0017: an explicit REVOKE of DELETE
    # is required, not just omitting it from GRANT -- this database auto-
    # grants tallyquo_app full CRUD on new... well, template isn't new, but
    # enabling RLS here is the first point grants on it actually matter,
    # so the same discipline applies. Templates are archived (archived_at),
    # never deleted, matching every other soft-delete table in this schema.
    op.execute("GRANT SELECT, INSERT, UPDATE ON template TO tallyquo_app")
    op.execute("REVOKE DELETE ON template FROM tallyquo_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON template")
    op.execute("ALTER TABLE template DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE business_profile DROP COLUMN default_template_id")
