from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.database import get_db as get_db
from fulfillment.config import settings
from fulfillment.models.user import User, UserRole
from fulfillment.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _demo_user() -> User:
    """A transient admin user used only in DEBUG (demo) mode when no token is sent."""
    return User(
        id="demo-user",
        email="demo@fulfillment.io",
        name="Demo User",
        password_hash="",
        role=UserRole.ADMIN,
        is_active=True,
        must_change_password=False,
    )


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if token:
        payload = decode_access_token(token)
        if payload is not None and payload.get("sub") is not None:
            user = await db.get(User, payload["sub"])
            if user is not None and user.is_active:
                return user
        if not settings.debug:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return _demo_user()

    if settings.debug:
        return _demo_user()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


async def require_operator_or_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin role required",
        )
    return current_user


async def get_current_user_id(
    current_user: Annotated[User, Depends(get_current_user)],
) -> str:
    return current_user.id
