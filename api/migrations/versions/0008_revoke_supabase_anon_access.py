"""Revoke Supabase's anon/authenticated role access to every table.

Supabase grants SELECT/INSERT/UPDATE/DELETE/TRUNCATE to `anon` and
`authenticated` on new public-schema tables by default (its platform
assumes PostgREST + RLS is the access pattern). This project's
architecture never uses PostgREST or Supabase client libraries at all --
the API connects directly as the `tallyquo_app` role from the FastAPI
backend (README.md "Why two DSNs") -- so those default grants are pure
unintended exposure, most seriously on the non-RLS tables
(email_tenant_lookup, session_token_lookup, otp_code, tax_rate, tenant):
those have zero protection against the public anon key, which is meant to
be embeddable client-side and is not a secret.

Guarded so this is a no-op on local Docker Postgres, which has no
anon/authenticated roles -- this is a Supabase-platform-specific
hardening step, not a portable part of the schema.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon')
             AND EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
            EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated';
            EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated';
            EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated';
            EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated';
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Deliberately irreversible -- restoring anon/authenticated access is a
    # manual, deliberate decision, never an automatic rollback.
    pass
