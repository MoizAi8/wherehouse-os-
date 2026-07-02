from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.config import settings
from fulfillment.database import async_session_factory

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict[str, str]:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated",
        )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return {
            "user_id": payload.get("sub", "unknown"),
            "role": payload.get("role", "viewer"),
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired token",
        )
