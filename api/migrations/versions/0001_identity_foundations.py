"""Identity foundations: tenant, app_user, session, otp_code + RLS + app_role.

Phase 0 workstreams 0.2-0.4 (implementation-plan.md). Tables and columns per
datamodel.md §3. This is the migration the adversarial RLS test suite in
tests/test_rls_isolation.py exercises directly.

Revision ID: 0001
Revises:
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- extensions -----------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # --- low-privilege app role (ADR-001) --------------------------------
    # No BYPASSRLS. This is the role the running API connects as; migrations
    # always run as the admin role, never this one. Password here is the
    # local-dev default from docker-compose.yml — staging/prod set a real
    # secret via ALTER ROLE ... PASSWORD out of band, never committed.
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'tallyquo_app') THEN
            CREATE ROLE tallyquo_app LOGIN PASSWORD 'tallyquo_app'
              NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION;
          END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          EXECUTE format('GRANT CONNECT ON DATABASE %I TO tallyquo_app', current_database());
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO tallyquo_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tallyquo_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO tallyquo_app"
    )

    # --- tenant -----------------------------------------------------------
    # Not itself tenant-scoped -- it IS the tenant. No RLS: every row is
    # globally readable-by-id only through application logic that has no
    # reason to list other tenants. (Composite-FK convention below starts
    # at app_user, the first table that references it.)
    op.execute(
        """
        CREATE TABLE tenant (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          status        text NOT NULL DEFAULT 'active',
          created_at    timestamptz NOT NULL DEFAULT now(),
          closed_at     timestamptz
        )
        """
    )

    # --- app_user -----------------------------------------------------------
    op.execute(
        """
        CREATE TABLE app_user (
          id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id          uuid NOT NULL REFERENCES tenant(id),
          email              citext NOT NULL,
          email_verified_at  timestamptz,
          created_at         timestamptz NOT NULL DEFAULT now(),
          last_seen_at       timestamptz,
          UNIQUE (email)
        )
        """
    )
    op.execute("CREATE INDEX ON app_user (tenant_id)")
    # Composite-FK convention (datamodel.md §9, implementation-plan.md 0.4):
    # every tenant-scoped table gets UNIQUE (tenant_id, id) so that anything
    # referencing this table can do so with a composite FK, making a
    # cross-tenant link a database-level impossibility rather than an
    # application bug.
    op.execute("ALTER TABLE app_user ADD UNIQUE (tenant_id, id)")

    op.execute(
        "ALTER TABLE app_user ENABLE ROW LEVEL SECURITY"
    )
    op.execute("ALTER TABLE app_user FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON app_user
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    # --- otp_code -----------------------------------------------------------
    # Not tenant-scoped: exists before a tenant does. Purged after 24h by a
    # retention job introduced alongside the auth endpoints in Phase 1.
    op.execute(
        """
        CREATE TABLE otp_code (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          email         citext NOT NULL,
          code_hash     bytea NOT NULL,
          expires_at    timestamptz NOT NULL,
          attempts      smallint NOT NULL DEFAULT 0,
          consumed_at   timestamptz,
          ip_hash       bytea,
          created_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ON otp_code (email, created_at DESC)")

    # --- session -----------------------------------------------------------
    op.execute(
        """
        CREATE TABLE session (
          id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id           uuid NOT NULL,
          user_id             uuid NOT NULL,
          refresh_token_hash  bytea NOT NULL,
          token_family        uuid NOT NULL,
          device_label        text,
          ip_hash             bytea,
          created_at          timestamptz NOT NULL DEFAULT now(),
          last_used_at        timestamptz,
          expires_at          timestamptz NOT NULL,
          revoked_at          timestamptz,
          FOREIGN KEY (tenant_id, user_id) REFERENCES app_user (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX ON session (tenant_id, user_id)")
    op.execute("ALTER TABLE session ADD UNIQUE (tenant_id, id)")

    op.execute("ALTER TABLE session ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE session FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON session
          USING      (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS session")
    op.execute("DROP TABLE IF EXISTS otp_code")
    op.execute("DROP TABLE IF EXISTS app_user")
    op.execute("DROP TABLE IF EXISTS tenant")
    # tallyquo_app role and extensions are left in place deliberately --
    # dropping a role/extension on downgrade risks breaking a live app
    # connection using it; role cleanup is a manual, deliberate operation.
