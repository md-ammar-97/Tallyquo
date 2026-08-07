"""Fixtures for the RLS adversarial suite.

The admin connection uses the local Postgres superuser, which bypasses RLS
regardless of FORCE — exactly the property needed to plant fixture rows for
two different tenants without going through tenant_session for setup. The
app connection is the real `tallyquo_app` role under test: no BYPASSRLS,
subject to every policy, which is what production traffic uses.
"""

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ADMIN_DSN = "postgresql+asyncpg://postgres:postgres@localhost:5435/tallyquo"
APP_DSN = "postgresql+asyncpg://tallyquo_app:tallyquo_app@localhost:5435/tallyquo"


@pytest_asyncio.fixture
async def admin_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(ADMIN_DSN)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def app_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(APP_DSN)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def two_tenants(admin_engine: AsyncEngine) -> AsyncIterator[dict[str, dict[str, UUID]]]:
    """Plants tenant A and tenant B, each with one app_user, as the admin
    role (bypasses RLS). Tears down after the test regardless of outcome.
    """
    async with admin_engine.begin() as conn:
        result = await conn.execute(
            text(
                "INSERT INTO tenant DEFAULT VALUES RETURNING id "
            )
        )
        tenant_a_id = result.scalar_one()
        result = await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        tenant_b_id = result.scalar_one()

        result = await conn.execute(
            text(
                "INSERT INTO app_user (tenant_id, email) VALUES (:tid, :email) RETURNING id"
            ),
            {"tid": tenant_a_id, "email": "a@tenant-a.example"},
        )
        user_a_id = result.scalar_one()
        result = await conn.execute(
            text(
                "INSERT INTO app_user (tenant_id, email) VALUES (:tid, :email) RETURNING id"
            ),
            {"tid": tenant_b_id, "email": "b@tenant-b.example"},
        )
        user_b_id = result.scalar_one()

    yield {
        "a": {"tenant_id": tenant_a_id, "user_id": user_a_id},
        "b": {"tenant_id": tenant_b_id, "user_id": user_b_id},
    }

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM app_user WHERE tenant_id IN (:a, :b)"),
            {"a": tenant_a_id, "b": tenant_b_id},
        )
        await conn.execute(
            text("DELETE FROM tenant WHERE id IN (:a, :b)"),
            {"a": tenant_a_id, "b": tenant_b_id},
        )


@pytest.fixture(autouse=True, scope="session")
def _event_loop_policy():
    # pytest-asyncio + asyncpg on Windows needs the selector loop, not proactor.
    import asyncio
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_cached_app_engine():
    """`tallyquo.core.db` caches a module-level engine — correct for a real
    process with exactly one event loop for its lifetime, wrong across
    pytest-asyncio tests where each test function gets its own loop. Without
    this, an engine created in test N's loop gets reused in test N+1 after
    its loop is closed. Only test code needs this reset; production never
    tears down its event loop mid-process.
    """
    import tallyquo.core.db as db_module

    db_module._engine = None
    db_module._session_factory = None
    yield
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None
