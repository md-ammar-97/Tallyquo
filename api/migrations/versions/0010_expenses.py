"""Expenses: expense_category, expense, receipt. Phase 2 workstreams 2.8-2.11.

Schema per datamodel.md §8. `expense_category` follows the `template`
table's system/tenant-owned split (migration 0006): system rows have
tenant_id = NULL and are readable by everyone, no RLS -- only system
rows exist for now (no custom-category workstream in Phase 2), so this
mirrors that precedent exactly rather than inventing a new one.

`itc_eligible` (E7/E8, P1) is computed and stored at write time, not
derived at read time like invoice status (L15) -- unlike an overdue
check against today's date, ITC eligibility is a fixed historical fact
anchored to expense_date vs. the business's registration_effective_date
at the time the expense was recorded. Nothing about it changes as time
passes, so there's no staleness risk in storing it directly.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE expense_source AS ENUM ('manual', 'ocr', 'recurring', 'import')")

    op.execute(
        """
        CREATE TABLE expense_category (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid,
          name          text NOT NULL,
          t2125_line    text,
          deductible_pct numeric(5,2) NOT NULL DEFAULT 100.00,
          is_capital    boolean NOT NULL DEFAULT false,
          cca_class     text,
          archived_at   timestamptz
        )
        """
    )
    # System categories (tenant_id NULL) must be visible regardless of
    # session context -- no RLS, same reasoning as the `template` table.
    op.execute("GRANT SELECT ON expense_category TO tallyquo_app")

    # T2125 line mapping is a starting point for categorization, not tax
    # advice (problem-statement.md: "no you-owe-$X phrasing" applies here
    # too -- categories are editable by the user's accountant at year-end).
    op.execute(
        """
        INSERT INTO expense_category (name, t2125_line, deductible_pct, is_capital) VALUES
        ('Advertising', '8521', 100.00, false),
        ('Meals & entertainment', '8523', 50.00, false),
        ('Office expenses', '8810', 100.00, false),
        ('Professional fees', '8860', 100.00, false),
        ('Supplies', '8811', 100.00, false),
        ('Travel', '9200', 100.00, false),
        ('Motor vehicle expenses', '9281', 100.00, false),
        ('Business-use-of-home', '9945', 100.00, false),
        ('Capital assets', NULL, 100.00, true),
        ('Other expenses', '9270', 100.00, false)
        """
    )

    op.execute(
        """
        CREATE TABLE expense (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          expense_date  date NOT NULL,
          vendor        text,
          description   text,
          category_id   uuid REFERENCES expense_category(id),
          currency      char(3) NOT NULL DEFAULT 'CAD',
          amount_total  numeric(14,2) NOT NULL,
          tax_amount    numeric(14,2) NOT NULL DEFAULT 0,
          tax_type      tax_type,
          amount_net    numeric(14,2) NOT NULL,
          fx_rate_to_cad numeric(14,8),
          amount_cad    numeric(14,2),
          business_use_pct numeric(5,2) NOT NULL DEFAULT 100.00,
          itc_eligible  boolean NOT NULL DEFAULT false,
          client_id     uuid,
          is_rebilled   boolean NOT NULL DEFAULT false,
          rebilled_invoice_id uuid,
          payment_method payment_method,
          source        expense_source NOT NULL DEFAULT 'manual',
          ocr_confidence numeric(4,3),
          ocr_raw       jsonb,
          created_at    timestamptz NOT NULL DEFAULT now(),
          deleted_at    timestamptz,
          UNIQUE (tenant_id, id),
          FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id),
          FOREIGN KEY (tenant_id, rebilled_invoice_id) REFERENCES invoice (tenant_id, id),
          CONSTRAINT amounts_consistent CHECK (
            abs(amount_net + tax_amount - amount_total) < 0.02
          )
        )
        """
    )
    op.execute("CREATE INDEX ON expense (tenant_id, expense_date DESC) WHERE deleted_at IS NULL")
    op.execute("ALTER TABLE expense ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE expense FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON expense
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON expense TO tallyquo_app")

    op.execute(
        """
        CREATE TABLE receipt (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          expense_id    uuid,
          file_ref      text NOT NULL,
          file_hash     bytea NOT NULL,
          mime_type     text NOT NULL,
          byte_size     integer NOT NULL,
          page_count    smallint,
          uploaded_at   timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, file_hash),
          FOREIGN KEY (tenant_id, expense_id) REFERENCES expense (tenant_id, id)
        )
        """
    )
    op.execute("ALTER TABLE receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE receipt FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON receipt
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON receipt TO tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS receipt")
    op.execute("DROP TABLE IF EXISTS expense")
    op.execute("DROP TABLE IF EXISTS expense_category")
    op.execute("DROP TYPE IF EXISTS expense_source")
