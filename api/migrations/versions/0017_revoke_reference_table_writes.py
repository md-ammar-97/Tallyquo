"""Revoke INSERT/UPDATE/DELETE on every read-only global reference
table. Discovered while adding income_tax_bracket/cpp_parameter
(0015/0016): this database has a default-privileges rule that grants
tallyquo_app full CRUD on any new table created by the postgres role,
so `GRANT SELECT ...` alone never actually withheld write access --
it just added to what the default privileges already gave.

That means tax_rate, tax_rate_version, and tax_threshold (0004, the
very first reference tables) have been writable by the running app
role since Phase 0, contradicting datamodel.md §10 ("read-only to the
app role ... no writes from the running API") and the whole point of
X20 (rate changes go through a reviewed migration pipeline, never a
bare write). No application code has ever issued a write to these
tables -- grep confirms it -- so this is pure hardening, not a
behaviour change.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "tax_rate_version",
    "tax_rate",
    "tax_threshold",
    "income_tax_bracket",
    "cpp_parameter",
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {table} FROM tallyquo_app")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"GRANT INSERT, UPDATE, DELETE ON {table} TO tallyquo_app")
