"""Clients, projects, client evidence. Phase 1 workstreams 1.6-1.7.

Tables per datamodel.md §5. `tax_treatment` is the enum the whole tax
engine's correctness depends on (problem-statement.md §5.1) -- storing a
rate instead of this enum is the defect the entire architecture exists to
prevent.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE tax_treatment AS ENUM "
        "('not_registered', 'taxable', 'zero_rated_export', 'exempt')"
    )
    op.execute(
        "CREATE TYPE evidence_kind AS ENUM "
        "('non_residency_attestation', 'contract', 'registration_certificate', 'other')"
    )

    op.execute(
        """
        CREATE TABLE client (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL REFERENCES tenant(id),
          legal_name    text NOT NULL,
          display_name  text,
          contact_name  text,
          email         citext,
          phone         text,

          address_line1 text,
          address_line2 text,
          city          text,
          region_code   text,
          postal_code   text,
          country_code  char(2) NOT NULL,

          tax_treatment tax_treatment NOT NULL,
          is_gst_registered boolean,
          treatment_override_reason text,

          default_currency char(3) NOT NULL DEFAULT 'CAD',
          default_payment_terms_days smallint,
          default_rate  numeric(14,2),
          default_template_id uuid,
          notes         text,

          created_at    timestamptz NOT NULL DEFAULT now(),
          archived_at   timestamptz,

          CONSTRAINT taxable_requires_region CHECK (
            tax_treatment <> 'taxable' OR region_code IS NOT NULL
          )
        )
        """
    )
    op.execute("ALTER TABLE client ADD UNIQUE (tenant_id, id)")
    op.execute("CREATE INDEX ON client (tenant_id, archived_at, legal_name)")
    op.execute("ALTER TABLE client ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE client FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON client
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE client_evidence (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          client_id     uuid NOT NULL,
          kind          evidence_kind NOT NULL,
          file_ref      text NOT NULL,
          file_hash     bytea NOT NULL,
          effective_date date,
          expires_at    date,
          note          text,
          uploaded_at   timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id)
        )
        """
    )
    op.execute("ALTER TABLE client_evidence ADD UNIQUE (tenant_id, id)")
    op.execute("ALTER TABLE client_evidence ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE client_evidence FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON client_evidence
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE project (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          client_id     uuid NOT NULL,
          name          text NOT NULL,
          code          text,
          default_rate  numeric(14,2),
          archived_at   timestamptz,
          FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id)
        )
        """
    )
    op.execute("ALTER TABLE project ADD UNIQUE (tenant_id, id)")
    op.execute("ALTER TABLE project ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON project
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project")
    op.execute("DROP TABLE IF EXISTS client_evidence")
    op.execute("DROP TABLE IF EXISTS client")
    op.execute("DROP TYPE IF EXISTS evidence_kind")
    op.execute("DROP TYPE IF EXISTS tax_treatment")
