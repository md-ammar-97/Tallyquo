"""Invoices: invoice_sequence, invoice, invoice_line, invoice_tax_line, credit_note.

Phase 1 workstreams 1.12-1.17. Schema per datamodel.md §7. `payment` and
`recurring_rule`/`recurring_run` are Phase 2 (implementation-plan.md
workstream 2.1, 2.6) and deliberately not created here.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE invoice_status AS ENUM "
        "('draft', 'issued', 'partially_paid', 'paid', 'overdue', 'cancelled')"
    )
    op.execute("CREATE TYPE line_unit AS ENUM ('hours', 'days', 'units', 'fixed')")

    op.execute(
        """
        CREATE TABLE invoice_sequence (
          tenant_id     uuid NOT NULL,
          scope_key     text NOT NULL,
          next_value    integer NOT NULL DEFAULT 1,
          PRIMARY KEY (tenant_id, scope_key)
        )
        """
    )
    op.execute("ALTER TABLE invoice_sequence ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoice_sequence FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON invoice_sequence
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE invoice (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          client_id     uuid NOT NULL,
          project_id    uuid,

          number        text,
          status        invoice_status NOT NULL DEFAULT 'draft',

          invoice_date  date,
          service_period_start date,
          service_period_end   date,
          payment_terms_days smallint,
          due_date      date,

          currency      char(3) NOT NULL DEFAULT 'CAD',
          fx_rate_to_cad numeric(14,8),
          fx_rate_date  date,
          fx_rate_source text,

          subtotal      numeric(14,2) NOT NULL DEFAULT 0,
          discount_amount numeric(14,2) NOT NULL DEFAULT 0,
          tax_total     numeric(14,2) NOT NULL DEFAULT 0,
          total         numeric(14,2) NOT NULL DEFAULT 0,
          amount_paid   numeric(14,2) NOT NULL DEFAULT 0,
          total_cad     numeric(14,2),

          tax_treatment_snapshot tax_treatment,
          tax_jurisdiction_snapshot text,
          tax_version_id uuid REFERENCES tax_rate_version(id),
          template_id   uuid,
          template_version integer,
          supplier_snapshot jsonb,
          client_snapshot   jsonb,

          po_reference  text,
          description   text,
          notes         text,
          footer_text   text,

          pdf_ref       text,
          pdf_hash      bytea,

          parent_invoice_id uuid,
          revision      smallint NOT NULL DEFAULT 0,

          created_at    timestamptz NOT NULL DEFAULT now(),
          issued_at     timestamptz,
          cancelled_at  timestamptz,
          cancel_reason text,

          UNIQUE (tenant_id, number),
          UNIQUE (tenant_id, id),
          FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id),

          CONSTRAINT issued_has_number CHECK (
            status = 'draft' OR (number IS NOT NULL AND issued_at IS NOT NULL
                                 AND invoice_date IS NOT NULL)
          ),
          CONSTRAINT issued_has_snapshot CHECK (
            status = 'draft' OR (tax_treatment_snapshot IS NOT NULL
                                 AND tax_version_id IS NOT NULL)
          ),
          CONSTRAINT paid_not_over CHECK (amount_paid <= total + 0.01)
        )
        """
    )
    op.execute("CREATE INDEX ON invoice (tenant_id, invoice_date DESC)")
    op.execute("CREATE INDEX ON invoice (tenant_id, client_id, invoice_date DESC)")
    op.execute(
        "CREATE INDEX ON invoice (tenant_id, status) "
        "WHERE status IN ('issued','partially_paid','overdue')"
    )
    op.execute("ALTER TABLE invoice ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoice FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON invoice
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE invoice_line (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          invoice_id    uuid NOT NULL,
          position      smallint NOT NULL,
          description   text NOT NULL,
          quantity      numeric(12,3) NOT NULL DEFAULT 1,
          unit          line_unit NOT NULL DEFAULT 'fixed',
          unit_rate     numeric(14,2) NOT NULL,
          amount        numeric(14,2) NOT NULL,
          is_taxable    boolean NOT NULL DEFAULT true,
          project_ref   text,
          FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id) ON DELETE CASCADE,
          UNIQUE (invoice_id, position)
        )
        """
    )
    op.execute("ALTER TABLE invoice_line ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoice_line FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON invoice_line
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE invoice_tax_line (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          invoice_id    uuid NOT NULL,
          tax_type      tax_type,
          label         text NOT NULL,
          rate          numeric(7,5),
          taxable_base  numeric(14,2) NOT NULL,
          amount        numeric(14,2) NOT NULL,
          display_note  text,
          position      smallint NOT NULL,
          FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id) ON DELETE CASCADE
        )
        """
    )
    op.execute("ALTER TABLE invoice_tax_line ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoice_tax_line FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON invoice_tax_line
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE credit_note (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          invoice_id    uuid NOT NULL,
          number        text NOT NULL,
          amount        numeric(14,2) NOT NULL,
          tax_amount    numeric(14,2) NOT NULL DEFAULT 0,
          currency      char(3) NOT NULL,
          reason        text NOT NULL,
          issued_at     timestamptz NOT NULL DEFAULT now(),
          pdf_ref       text,
          UNIQUE (tenant_id, number),
          FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id)
        )
        """
    )
    op.execute("ALTER TABLE credit_note ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE credit_note FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON credit_note
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS credit_note")
    op.execute("DROP TABLE IF EXISTS invoice_tax_line")
    op.execute("DROP TABLE IF EXISTS invoice_line")
    op.execute("DROP TABLE IF EXISTS invoice")
    op.execute("DROP TABLE IF EXISTS invoice_sequence")
    op.execute("DROP TYPE IF EXISTS line_unit")
    op.execute("DROP TYPE IF EXISTS invoice_status")
