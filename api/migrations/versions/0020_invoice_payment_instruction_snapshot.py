"""Closes a real, previously-undiscovered gap found while starting
Phase 4 workstream 4.2: `payment_instruction` (1.4) has existed since
Phase 1, with full CRUD and column-level encryption, but nothing in
the invoice issuance or PDF rendering path ever read it. Every
invoice this product has ever issued shows the client no way to
actually pay -- despite `design.md` §9's own layout spec ("then
payment instructions, then footer") and every system template's
`blocks` array already listing "payment".

`payment_instruction_snapshot` follows the exact same pattern as
`supplier_snapshot`/`client_snapshot` (0007): frozen, decrypted, at
issue time. Frozen because a client re-downloading an old invoice
must see the same bank details they were originally given, not
whatever the tenant's payment instructions happen to be today (X4/L14's
"byte-identical forever" guarantee extends to this the same way it
already does to the tax computation). Decrypted because the PDF is
going to a third party who needs the real numbers to pay -- masking
is a UI protection for the tenant's own session, not appropriate on
the document itself.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE invoice ADD COLUMN payment_instruction_snapshot jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE invoice DROP COLUMN payment_instruction_snapshot")
