"""Tax reference data: tax_rate_version, tax_rate, tax_threshold.

Phase 1 workstream 1.9. The only global (non-tenant-scoped) tables besides
`tenant` itself -- datamodel.md §6. The EXCLUDE constraint is the load-
bearing line: it makes overlapping effective periods for the same
(jurisdiction, tax_type) impossible at the database level, so a bad rate
update cannot create ambiguity about which rate applied on a given date.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE tax_type AS ENUM ('gst', 'hst', 'pst', 'qst', 'rst')")

    op.execute(
        """
        CREATE TABLE tax_rate_version (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          label         text NOT NULL,
          published_at  timestamptz NOT NULL DEFAULT now(),
          approved_by   text NOT NULL,
          source_note   text
        )
        """
    )

    # Needed before the EXCLUDE constraint below -- GiST indexes need
    # btree_gist's operator classes to support `=` on char/text/enum.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.execute(
        """
        CREATE TABLE tax_rate (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          version_id    uuid NOT NULL REFERENCES tax_rate_version(id),
          country_code  char(2) NOT NULL,
          region_code   text,
          tax_type      tax_type NOT NULL,
          rate          numeric(7,5) NOT NULL,
          label         text NOT NULL,
          compounds_on_gst boolean NOT NULL DEFAULT false,
          effective_from date NOT NULL,
          effective_to  date,
          source_url    text NOT NULL,
          EXCLUDE USING gist (
            country_code WITH =, region_code WITH =, tax_type WITH =,
            daterange(effective_from, effective_to) WITH &&
          )
        )
        """
    )

    op.execute(
        """
        CREATE TABLE tax_threshold (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          country_code  char(2) NOT NULL,
          kind          text NOT NULL,
          amount        numeric(14,2) NOT NULL,
          effective_from date NOT NULL,
          effective_to  date,
          source_url    text NOT NULL
        )
        """
    )

    # Global tables are read-only to the app role and exempt from RLS
    # (datamodel.md §10) -- SELECT only, no writes from the running API.
    op.execute("GRANT SELECT ON tax_rate_version, tax_rate, tax_threshold TO tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tax_threshold")
    op.execute("DROP TABLE IF EXISTS tax_rate")
    op.execute("DROP TABLE IF EXISTS tax_rate_version")
    op.execute("DROP TYPE IF EXISTS tax_type")
