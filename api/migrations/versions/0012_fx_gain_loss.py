"""Adds payment.fx_gain_loss. Phase 2 workstreams 2.4-2.5.

edgecases.md C3: "Payment arrives at a different rate than the invoice |
FX gain/loss recorded explicitly as its own figure. Not silently
absorbed into revenue." This is that figure -- computed once at payment
time (this payment's own rate vs. the invoice's frozen issue-time rate,
C4) and stored, not re-derived later against a rate that will have
moved on.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE payment ADD COLUMN fx_gain_loss numeric(14,2)")


def downgrade() -> None:
    op.execute("ALTER TABLE payment DROP COLUMN IF EXISTS fx_gain_loss")
