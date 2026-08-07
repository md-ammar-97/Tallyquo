"""Income tax bracket + CPP parameter reference data. Phase 3 workstream
3.1 -- datamodel.md §6.

Modelled the same way as `tax_rate` (0004): data with a lifetime, never
hardcoded into the projection engine, effective-dated so a historical
projection can be recomputed identically. The EXCLUDE constraint on
`income_tax_bracket` is the load-bearing line, same role as tax_rate's --
it makes overlapping (jurisdiction, income range, effective period)
combinations impossible at the database level.

`jurisdiction` is 'federal' or a two-letter province/territory code.
Quebec is deliberately absent -- QPP replaces CPP entirely and Quebec
runs its own separate income tax system (Revenu Québec), which is
explicitly Phase 4 scope (implementation_plan.md 4.4), not Phase 3.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE income_tax_bracket (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          jurisdiction  text NOT NULL,
          income_from   numeric(14,2) NOT NULL,
          income_to     numeric(14,2),
          rate          numeric(7,5) NOT NULL,
          effective_from date NOT NULL,
          effective_to  date,
          source_url    text NOT NULL,
          EXCLUDE USING gist (
            jurisdiction WITH =,
            numrange(income_from, income_to) WITH &&,
            daterange(effective_from, effective_to) WITH &&
          )
        )
        """
    )

    op.execute(
        """
        CREATE TABLE cpp_parameter (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          basic_exemption numeric(12,2) NOT NULL,
          ympe          numeric(12,2) NOT NULL,
          yampe         numeric(12,2) NOT NULL,
          employee_rate numeric(6,5) NOT NULL,
          self_employed_rate numeric(6,5) NOT NULL,
          cpp2_employee_rate numeric(6,5) NOT NULL,
          cpp2_self_employed_rate numeric(6,5) NOT NULL,
          effective_from date NOT NULL,
          effective_to  date,
          source_url    text NOT NULL,
          EXCLUDE USING gist (daterange(effective_from, effective_to) WITH &&)
        )
        """
    )

    # Global, read-only reference tables -- same grant shape as tax_rate*
    # (datamodel.md §10): SELECT only, no writes from the running API,
    # exempt from RLS since there is no tenant_id column.
    op.execute("GRANT SELECT ON income_tax_bracket, cpp_parameter TO tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cpp_parameter")
    op.execute("DROP TABLE IF EXISTS income_tax_bracket")
