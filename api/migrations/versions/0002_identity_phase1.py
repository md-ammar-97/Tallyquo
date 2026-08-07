"""Identity Phase 1: email->tenant auth lookup, business profile, payment instructions.

Phase 1 workstreams 1.3-1.4 (implementation-plan.md). Tables per
datamodel.md §4, plus `email_tenant_lookup` which datamodel.md doesn't
define but is needed in practice: `app_user` is RLS-FORCEd, so an
unauthenticated request (verify-otp, before any tenant context exists) has
no way to discover which tenant an email belongs to without either a
bypass-RLS credential (which the deployed app deliberately never holds --
see README "Why two DSNs") or this narrow, non-RLS auxiliary index. It
holds no data beyond what `app_user`'s own `UNIQUE(email)` already
guarantees is globally unique; it exists purely to make that fact
queryable pre-authentication, the same way `tenant` and `otp_code` are
also unscoped because they precede/bootstrap tenancy.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE email_tenant_lookup (
          email      citext PRIMARY KEY,
          tenant_id  uuid NOT NULL REFERENCES tenant(id),
          user_id    uuid NOT NULL
        )
        """
    )

    # Same bootstrap problem as email_tenant_lookup, for refresh tokens: a
    # /auth/refresh call has a token but no tenant context yet, and `session`
    # is RLS-FORCEd. Rows are append-only (never deleted/updated) even across
    # rotations -- a hash that resolves here but whose `session` row is
    # revoked is exactly the replay signal architecture.md §5 asks for
    # ("detect replay -> revoke family"), which requires the old hash to
    # stay resolvable after rotation, not disappear.
    op.execute(
        """
        CREATE TABLE session_token_lookup (
          token_hash bytea PRIMARY KEY,
          tenant_id  uuid NOT NULL REFERENCES tenant(id),
          session_id uuid NOT NULL
        )
        """
    )

    op.execute("CREATE TYPE registration_status AS ENUM ('not_registered', 'registration_pending', 'registered')")

    op.execute(
        """
        CREATE TABLE business_profile (
          tenant_id     uuid PRIMARY KEY REFERENCES tenant(id),
          legal_name    text NOT NULL,
          operating_name text,
          sole_prop_label text NOT NULL DEFAULT 'sole proprietor, operating as',

          address_line1 text NOT NULL,
          address_line2 text,
          city          text NOT NULL,
          region_code   text NOT NULL,
          postal_code   text NOT NULL,
          country_code  char(2) NOT NULL DEFAULT 'CA',

          email         citext,
          phone         text,
          website       text,
          social_links  jsonb NOT NULL DEFAULT '[]',

          logo_ref      text,
          logo_dark_ref text,

          registration_status registration_status NOT NULL DEFAULT 'not_registered',
          gst_hst_number text,
          registration_effective_date date,
          qst_number    text,
          pst_numbers   jsonb NOT NULL DEFAULT '{}',

          default_currency char(3) NOT NULL DEFAULT 'CAD',
          default_payment_terms_days smallint NOT NULL DEFAULT 30,
          invoice_number_format text NOT NULL DEFAULT '{PREFIX}-{YYYY}-{NNN}',
          invoice_number_prefix text NOT NULL DEFAULT 'INV',
          fiscal_year_start_month smallint NOT NULL DEFAULT 1,
          timezone      text NOT NULL DEFAULT 'America/Toronto',
          gst_filing_frequency text,

          created_at    timestamptz NOT NULL DEFAULT now(),
          updated_at    timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT registered_requires_bn CHECK (
            registration_status <> 'registered'
            OR (gst_hst_number IS NOT NULL AND registration_effective_date IS NOT NULL)
          )
        )
        """
    )
    op.execute("ALTER TABLE business_profile ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE business_profile FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON business_profile
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute("CREATE TYPE payment_method AS ENUM ('eft', 'ach', 'wire', 'cheque', 'cash', 'card', 'etransfer', 'other')")

    op.execute(
        """
        CREATE TABLE payment_instruction (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id     uuid NOT NULL REFERENCES tenant(id),
          label         text NOT NULL,
          method        payment_method NOT NULL,
          provider      text,
          account_holder text,
          currency      char(3) NOT NULL,
          fields_encrypted bytea,
          is_default    boolean NOT NULL DEFAULT false,
          archived_at   timestamptz
        )
        """
    )
    op.execute("ALTER TABLE payment_instruction ADD UNIQUE (tenant_id, id)")
    op.execute("ALTER TABLE payment_instruction ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payment_instruction FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON payment_instruction
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payment_instruction")
    op.execute("DROP TYPE IF EXISTS payment_method")
    op.execute("DROP TABLE IF EXISTS business_profile")
    op.execute("DROP TYPE IF EXISTS registration_status")
    op.execute("DROP TABLE IF EXISTS session_token_lookup")
    op.execute("DROP TABLE IF EXISTS email_tenant_lookup")
