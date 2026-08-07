from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from tallyquo.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        # NullPool-friendly settings deferred until real load profile is known
        # (architecture.md §15: near-flat for 25 days, spike at month end).
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def raw_session() -> AsyncIterator[AsyncSession]:
    """A session with no tenant context set.

    Only for use before a tenant is known to exist (OTP request/verify) or by
    code that has its own explicit reason to bypass tenant scoping. RLS with
    no `app.tenant_id` set fails closed (see tenant_context.py) — this is not
    a bypass, it is "no tenant filter has been established yet."
    """
    async with get_session_factory()() as session:
        yield session
