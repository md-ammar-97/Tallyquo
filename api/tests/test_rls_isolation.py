"""Adversarial cross-tenant probe (implementation-plan.md 0.5).

This is the merge-gate suite architecture.md §4 requires: authenticate as
tenant A, try to reach tenant B's resources, assert it's impossible. At
Phase 0 there are no product routes yet, so the probe runs directly against
the RLS policies these migrations establish -- the same guarantee, one
layer down. As Phase 1 adds real HTTP routes, an equivalent probe should be
added per-route on top of this DB-level suite, not instead of it.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tallyquo.core.tenant_context import tenant_session


@pytest.mark.asyncio
async def test_tenant_a_cannot_see_tenant_b_rows(two_tenants: dict) -> None:
    """edgecases.md T1/T6: a tenant-scoped query never returns another
    tenant's row, even though it physically exists in the same table."""
    tenant_a = two_tenants["a"]["tenant_id"]
    tenant_b_user = two_tenants["b"]["user_id"]

    async with tenant_session(tenant_a) as session:
        result = await session.execute(
            text("SELECT id FROM app_user WHERE id = :uid"),
            {"uid": tenant_b_user},
        )
        assert result.first() is None


@pytest.mark.asyncio
async def test_tenant_a_sees_only_its_own_rows(two_tenants: dict) -> None:
    tenant_a = two_tenants["a"]["tenant_id"]
    user_a = two_tenants["a"]["user_id"]

    async with tenant_session(tenant_a) as session:
        result = await session.execute(text("SELECT id FROM app_user"))
        ids = {row[0] for row in result.all()}
        assert ids == {user_a}


@pytest.mark.asyncio
async def test_cannot_write_a_row_claiming_another_tenant(two_tenants: dict) -> None:
    """edgecases.md T4: WITH CHECK rejects a write, not just a read, that
    claims a tenant_id other than the session's own -- this is the case a
    bare `USING` clause with no `WITH CHECK` would miss."""
    tenant_a = two_tenants["a"]["tenant_id"]
    tenant_b = two_tenants["b"]["tenant_id"]

    with pytest.raises(DBAPIError):
        async with tenant_session(tenant_a) as session:
            await session.execute(
                text(
                    "INSERT INTO app_user (tenant_id, email) "
                    "VALUES (:tid, :email)"
                ),
                {"tid": tenant_b, "email": f"leaked-{uuid4()}@example.com"},
            )


@pytest.mark.asyncio
async def test_missing_tenant_context_fails_closed(app_engine: AsyncEngine) -> None:
    """edgecases.md T2, P1: a query issued through the app role with no
    `app.tenant_id` ever set must error, never silently return all rows or
    zero rows framed as a normal empty result. This is what makes "the
    middleware forgot to set tenant context" a loud failure, not a quiet
    data leak or a quiet false negative."""
    async with app_engine.connect() as conn:
        with pytest.raises(DBAPIError, match="app.tenant_id"):
            await conn.execute(text("SELECT * FROM app_user"))


@pytest.mark.asyncio
async def test_app_role_has_no_bypassrls(admin_engine: AsyncEngine) -> None:
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT rolbypassrls, rolsuper FROM pg_roles "
                "WHERE rolname = 'tallyquo_app'"
            )
        )
        row = result.one()
        assert row.rolbypassrls is False
        assert row.rolsuper is False


@pytest.mark.parametrize("table_name", ["app_user", "session"])
@pytest.mark.asyncio
async def test_rls_enabled_and_forced(admin_engine: AsyncEngine, table_name: str) -> None:
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = :t"
            ),
            {"t": table_name},
        )
        row = result.one()
        assert row.relrowsecurity is True, f"{table_name} does not have RLS enabled"
        assert row.relforcerowsecurity is True, f"{table_name} does not FORCE RLS"


@pytest.mark.parametrize("table_name", ["app_user", "session"])
@pytest.mark.asyncio
async def test_composite_tenant_id_unique_constraint(
    admin_engine: AsyncEngine, table_name: str
) -> None:
    """datamodel.md §9 / implementation-plan.md 0.4: every tenant-scoped
    table carries UNIQUE (tenant_id, id) so anything referencing it can use
    a composite FK, making a cross-tenant link impossible at the DB level."""
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT count(*) FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = :t AND c.contype = 'u'
                  AND (
                    SELECT array_agg(k ORDER BY k) FROM unnest(c.conkey) k
                  ) = (
                    SELECT array_agg(a.attnum ORDER BY a.attnum)
                    FROM pg_attribute a
                    WHERE a.attrelid = t.oid AND a.attname IN ('tenant_id', 'id')
                  )
                """
            ),
            {"t": table_name},
        )
        assert result.scalar_one() >= 1, (
            f"{table_name} is missing a UNIQUE (tenant_id, id) constraint"
        )


@pytest.mark.asyncio
async def test_tenant_session_sets_actor_id(two_tenants: dict) -> None:
    tenant_a = two_tenants["a"]["tenant_id"]
    actor = uuid4()
    async with tenant_session(tenant_a, actor_id=actor) as session:
        result = await session.execute(text("SELECT current_setting('app.actor_id')"))
        assert UUID(result.scalar_one()) == actor
