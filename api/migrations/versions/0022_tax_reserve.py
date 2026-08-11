"""Carbon redesign Dashboard's Tax Reserve progress section
(dashboard_design.md §7): "how much have I actually moved into a tax
reserve account" vs. the already-existing recommended amount
(projection.set_aside.total_estimated_tax_and_cpp). One row per tenant
per calendar year, mirroring income_declaration's (0018) exact shape --
same user-enterable-figure-alongside-a-derived-one pattern.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tax_reserve (
          tenant_id     uuid NOT NULL,
          year          smallint NOT NULL,
          reserved_amount numeric(14,2) NOT NULL,
          updated_at    timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (tenant_id, year)
        )
        """
    )
    op.execute("ALTER TABLE tax_reserve ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tax_reserve FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON tax_reserve
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tax_reserve TO tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tax_reserve")
