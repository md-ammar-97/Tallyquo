"""Declared income mode. Phase 3 workstream 3.4 -- one row per
tenant per calendar year, holding the user's own annual income
target. P3: shown alongside the derived (extrapolated) figure, gap
displayed, never silently preferring one over the other.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE income_declaration (
          tenant_id     uuid NOT NULL,
          year          smallint NOT NULL,
          declared_annual_income numeric(14,2) NOT NULL,
          updated_at    timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (tenant_id, year)
        )
        """
    )
    op.execute("ALTER TABLE income_declaration ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE income_declaration FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON income_declaration
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON income_declaration TO tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS income_declaration")
