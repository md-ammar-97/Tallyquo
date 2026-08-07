from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.db import get_session_factory


@asynccontextmanager
async def tenant_session(
    tenant_id: UUID, actor_id: UUID | None = None
) -> AsyncIterator[AsyncSession]:
    """The only place `app.tenant_id` is ever set (architecture.md §4, step 5).

    Opens a transaction, sets the tenant — and, when known, the actor — via
    `SET LOCAL`, scoped to this transaction only so it can never leak across
    a pooled connection to a later, differently-scoped request. Every query
    made through the yielded session is then filtered by RLS automatically.
    Commits on clean exit; rolls back (discarding any `audit_log` rows
    written in the same transaction) on error.

    `tenant_id` has no default. There is deliberately no way to call this
    without one — "forgetting" to scope a request or a background job should
    be a type error, not a runtime bug (edgecases.md T2, T3).
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            # `SET LOCAL` doesn't accept bind parameters over the extended
            # query protocol asyncpg uses ("syntax error at or near $1").
            # set_config() is a real function, so it parameterizes normally;
            # the `true` third argument gives the same transaction-local
            # scoping SET LOCAL would.
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            if actor_id is not None:
                await session.execute(
                    text("SELECT set_config('app.actor_id', :actor_id, true)"),
                    {"actor_id": str(actor_id)},
                )
            yield session
