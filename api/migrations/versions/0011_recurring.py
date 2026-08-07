"""Recurring invoices: recurring_rule, recurring_run.
Phase 2 workstreams 2.6-2.7. Schema per datamodel.md §8.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE recurrence_cadence AS ENUM "
        "('weekly', 'biweekly', 'monthly', 'quarterly', 'semiannual', 'annual')"
    )

    op.execute(
        """
        CREATE TABLE recurring_rule (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          client_id     uuid NOT NULL,
          source_invoice_id uuid,
          cadence       recurrence_cadence NOT NULL,
          day_of_period smallint,
          next_run_date date NOT NULL,
          end_date      date,
          occurrences_remaining smallint,
          auto_issue    boolean NOT NULL DEFAULT false,
          is_paused     boolean NOT NULL DEFAULT false,
          last_run_date date,
          created_at    timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, id),
          FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id),
          FOREIGN KEY (tenant_id, source_invoice_id) REFERENCES invoice (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX ON recurring_rule (tenant_id) WHERE is_paused = false")
    op.execute("ALTER TABLE recurring_rule ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE recurring_rule FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON recurring_rule
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON recurring_rule TO tallyquo_app")

    op.execute(
        """
        CREATE TABLE recurring_run (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          rule_id       uuid NOT NULL,
          occurrence_date date NOT NULL,
          invoice_id    uuid,
          outcome       text NOT NULL,
          detail        text,
          created_at    timestamptz NOT NULL DEFAULT now(),
          UNIQUE (rule_id, occurrence_date),
          FOREIGN KEY (tenant_id, rule_id) REFERENCES recurring_rule (tenant_id, id),
          FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id)
        )
        """
    )
    op.execute("ALTER TABLE recurring_run ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE recurring_run FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON recurring_run
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON recurring_run TO tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recurring_run")
    op.execute("DROP TABLE IF EXISTS recurring_rule")
    op.execute("DROP TYPE IF EXISTS recurrence_cadence")
