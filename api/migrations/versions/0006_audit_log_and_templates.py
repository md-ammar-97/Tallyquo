"""audit_log + template. Prerequisites for invoice issuance.

audit_log: implementation-plan.md §7 lists this as a cross-cutting
requirement from Phase 0 onward, but Phase 0 was pure tenancy/RLS infra
with nothing yet to audit -- it's added here because invoice issuance
(next migration) is the first mutation that needs it. Append-only:
UPDATE/DELETE are revoked from the app role entirely (datamodel.md §11),
so a compromised app role cannot rewrite history, only add to it.

template: minimal version of datamodel.md §8 -- structured {theme, blocks}
JSON, no user-authored HTML/CSS (architecture.md §12). Full template
CRUD/editing is workstream 1.19-1.20; this migration only adds enough to
seed 3 system templates so invoice issuance has a real template_id to pin.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_log (
          id            bigserial PRIMARY KEY,
          tenant_id     uuid NOT NULL,
          actor_user_id uuid,
          actor_kind    text NOT NULL,
          action        text NOT NULL,
          entity_type   text NOT NULL,
          entity_id     uuid NOT NULL,
          before        jsonb,
          after         jsonb,
          request_id    text,
          ip_hash       bytea,
          occurred_at   timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ON audit_log (tenant_id, entity_type, entity_id, occurred_at DESC)")
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON audit_log
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT ON audit_log TO tallyquo_app")
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM tallyquo_app")
    op.execute("GRANT USAGE ON SEQUENCE audit_log_id_seq TO tallyquo_app")

    op.execute(
        """
        CREATE TABLE template (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid,
          name          text NOT NULL,
          schema_version integer NOT NULL DEFAULT 1,
          version       integer NOT NULL DEFAULT 1,
          theme         jsonb NOT NULL,
          blocks        jsonb NOT NULL,
          is_system     boolean NOT NULL DEFAULT false,
          is_default    boolean NOT NULL DEFAULT false,
          archived_at   timestamptz,
          created_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # System templates have tenant_id = NULL and are readable by everyone;
    # tenant-owned custom templates (Phase 4) get RLS once that path exists.
    # No RLS yet: only system rows exist in Phase 1, and NULL tenant_id
    # rows must be visible regardless of session context.
    op.execute("GRANT SELECT ON template TO tallyquo_app")

    op.execute(
        """
        INSERT INTO template (name, theme, blocks, is_system, is_default) VALUES
        ('Classic', '{"accent_color": "#0D99FF", "font_scale": 1.0}',
         '["supplier", "document", "bill_to", "services", "totals", "payment", "footer"]',
         true, true),
        ('Minimal', '{"accent_color": "#757575", "font_scale": 1.0}',
         '["supplier", "document", "bill_to", "services", "totals", "payment"]',
         true, false),
        ('Modern', '{"accent_color": "#A259FF", "font_scale": 1.0}',
         '["supplier", "document", "bill_to", "services", "totals", "payment", "footer"]',
         true, false)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS template")
    op.execute("DROP TABLE IF EXISTS audit_log")
