"""FastAPI auth dependencies, shared by every module's protected routes.

Two dependencies compose: `get_current_user` verifies the access token and
resolves who's asking; `get_db` wraps `tenant_context.tenant_session` around
that identity so every query in the route handler is automatically RLS-
scoped (architecture.md §4 steps 3-5) without the handler ever touching
tenant_id directly.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.logging import bind_tenant_context
from tallyquo.core.security import InvalidAccessToken, decode_access_token
from tallyquo.core.tenant_context import tenant_session


@dataclass(frozen=True)
class CurrentUser:
    tenant_id: UUID
    user_id: UUID
    session_id: UUID


async def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_access_token(token)
    except InvalidAccessToken:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None

    current_user = CurrentUser(
        tenant_id=UUID(payload["tenant_id"]),
        user_id=UUID(payload["user_id"]),
        session_id=UUID(payload["session_id"]),
    )
    bind_tenant_context(str(current_user.tenant_id))
    return current_user


async def get_db(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[AsyncSession]:
    async with tenant_session(current_user.tenant_id, actor_id=current_user.user_id) as session:
        yield session
