"""Public shareable invoice links. Phase 2 workstream 2.12-2.13, reframed
per user direction: no email sending, no sender-domain verification --
a durable, revocable public view/download link instead.

Same bootstrap-lookup pattern as identity's email_tenant_lookup /
session_token_lookup (architecture.md §5): a public request carries a
token but no tenant context yet, and `invoice` is RLS-FORCEd, so
token -> tenant_id resolution happens via a lookup table with no RLS
of its own. The token is hashed there (mirrors session_token_lookup),
so a read of this table alone can't reconstruct a working link;
`invoice.share_token` holds the plaintext so the owner can retrieve
and copy it.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE invoice ADD COLUMN share_token text UNIQUE")

    op.execute(
        """
        CREATE TABLE invoice_share_lookup (
          token_hash  bytea PRIMARY KEY,
          tenant_id   uuid NOT NULL,
          invoice_id  uuid NOT NULL,
          created_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON invoice_share_lookup TO tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS invoice_share_lookup")
    op.execute("ALTER TABLE invoice DROP COLUMN IF EXISTS share_token")
