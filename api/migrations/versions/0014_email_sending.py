"""User-configured SMTP + invoice email sending. Phase 2 workstreams
2.16-2.17. Schema per datamodel.md §4.

`email_account.credentials_encrypted` uses the same column-level
encryption as `payment_instruction.fields_encrypted` (core/security.py
encrypt_fields/decrypt_fields) -- a secret credential, never returned
to the client in full.

`invoice_email_log` is append-only like `audit_log`: every row is one
explicit, human-initiated send (edgecases.md O1, O7, O9), and UPDATE/
DELETE are revoked from the app role so the record can't be quietly
edited after the fact.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE email_account (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          label         text NOT NULL,
          from_name     text NOT NULL,
          from_address  citext NOT NULL,
          smtp_host     text NOT NULL,
          smtp_port     smallint NOT NULL,
          smtp_security text NOT NULL DEFAULT 'starttls',
          smtp_username text NOT NULL,
          credentials_encrypted bytea NOT NULL,
          is_default    boolean NOT NULL DEFAULT false,
          verified_at   timestamptz,
          created_at    timestamptz NOT NULL DEFAULT now(),
          archived_at   timestamptz,
          UNIQUE (tenant_id, id),
          CONSTRAINT email_account_security_check CHECK (smtp_security IN ('starttls', 'tls', 'none'))
        )
        """
    )
    op.execute("ALTER TABLE email_account ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE email_account FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON email_account
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON email_account TO tallyquo_app")

    op.execute(
        """
        CREATE TABLE invoice_email_log (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL,
          invoice_id    uuid NOT NULL,
          email_account_id uuid NOT NULL,
          to_addresses  jsonb NOT NULL,
          cc_addresses  jsonb NOT NULL DEFAULT '[]',
          subject       text NOT NULL,
          body          text NOT NULL,
          attached_invoice_pdf boolean NOT NULL DEFAULT true,
          extra_attachments jsonb NOT NULL DEFAULT '[]',
          sent_by_user_id uuid,
          status        text NOT NULL,
          error_detail  text,
          sent_at       timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id),
          FOREIGN KEY (tenant_id, email_account_id) REFERENCES email_account (tenant_id, id),
          CONSTRAINT invoice_email_log_status_check CHECK (status IN ('sent', 'failed'))
        )
        """
    )
    op.execute("CREATE INDEX ON invoice_email_log (tenant_id, invoice_id, sent_at DESC)")
    op.execute("ALTER TABLE invoice_email_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoice_email_log FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON invoice_email_log
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    # Append-only, same as audit_log -- no UPDATE/DELETE for the app role.
    op.execute("GRANT SELECT, INSERT ON invoice_email_log TO tallyquo_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS invoice_email_log")
    op.execute("DROP TABLE IF EXISTS email_account")
