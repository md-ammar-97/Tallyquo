"""Payments. Phase 2 workstreams 2.1-2.2.

Schema per datamodel.md §7. Invoice status transitions (issued ->
partially_paid/paid/overdue) are deliberately NOT stored as a direct
write target here -- edgecases.md L15: "Overdue status | Computed, not
stored -- derived from due_date < today AND amount_paid < total. Never a
stale stored flag." The `status` column keeps draft/issued/cancelled as
its only directly-written values; billing/invoices_service.py computes
the effective status (paid/partially_paid/overdue) at read time.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE payment (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          invoice_id    uuid NOT NULL,
          amount        numeric(14,2) NOT NULL,
          currency      char(3) NOT NULL,
          amount_cad    numeric(14,2),
          fx_rate_to_cad numeric(14,8),
          received_date date NOT NULL,
          method        payment_method,
          reference     text,
          note          text,
          created_at    timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX ON payment (tenant_id, invoice_id)")
    op.execute("ALTER TABLE payment ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payment FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON payment
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON payment TO tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payment")
