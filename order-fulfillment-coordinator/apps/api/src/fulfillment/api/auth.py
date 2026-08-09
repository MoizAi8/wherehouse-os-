from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_current_user, get_db, require_admin
from fulfillment.config import settings
from fulfillment.models.refresh_token import RefreshToken
from fulfillment.models.user import User, UserRole
from fulfillment.security import (
    create_access_token,
    generate_refresh_token,
    generate_reset_token,
    hash_password,
    hash_refresh_token,
    hash_reset_token,
    verify_password,
)
from fulfillment.tools.notifications import send_email_notification

logger = logging.getLogger("fulfillment.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: UserRole
    must_change_password: bool = False


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _create_tokens(db: AsyncSession, user: User) -> LoginResponse:
    access_token = create_access_token(user.id, user.role.value)
    raw_refresh = generate_refresh_token()
    refresh = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expiration_days),
        revoked=False,
    )
    db.add(refresh)
    await db.flush()
    return LoginResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.jwt_expiration_minutes * 60,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            must_change_password=user.must_change_password,
        ),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        name=body.name.strip(),
        role=UserRole.VIEWER,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    logger.info("Registered user %s", user.email)
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    logger.info("Login success for %s", user.email)
    return await _create_tokens(db, user)


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    token_hash = hash_refresh_token(body.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked.is_(False),
        )
    )
    refresh = result.scalar_one_or_none()
    if refresh is None or (_ensure_aware(refresh.expires_at) or datetime.min.replace(tzinfo=timezone.utc)) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = await db.get(User, refresh.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )
    refresh.revoked = True
    await db.flush()
    logger.info("Token refresh for %s", user.email)
    return await _create_tokens(db, user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    token_hash = hash_refresh_token(body.refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    refresh = result.scalar_one_or_none()
    if refresh is not None:
        refresh.revoked = True
        await db.flush()
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        must_change_password=current_user.must_change_password,
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = hash_password(body.new_password)
    current_user.must_change_password = False
    await db.flush()
    logger.info("Password changed for %s", current_user.email)
    return MessageResponse(message="Password changed")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is not None:
        token = generate_reset_token()
        user.password_reset_token_hash = hash_reset_token(token)
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_password_reset_expiration_minutes
        )
        await db.flush()
        # Send the reset link via email (never log the raw token).
        reset_link = f"{settings.reset_email_redirect_url.rstrip('/')}/reset-password?token={token}"
        body_text = (
            f"Reset your password:\n{reset_link}\n\n"
            f"This link expires in {settings.jwt_password_reset_expiration_minutes} minutes."
        )
        await send_email_notification(
            db=db,
            recipient=user.email,
            subject="Reset your password",
            body=body_text,
        )
    return MessageResponse(message="If that email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    token_hash = hash_reset_token(body.token)
    result = await db.execute(select(User).where(User.password_reset_token_hash == token_hash))
    user = result.scalar_one_or_none()
    if (
        user is None
        or _ensure_aware(user.password_reset_expires_at) is None
        or (_ensure_aware(user.password_reset_expires_at) or datetime.min.replace(tzinfo=timezone.utc))
        < datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.password_hash = hash_password(body.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.must_change_password = False
    await db.flush()
    logger.info("Password reset for %s", user.email)
    return MessageResponse(message="Password has been reset")


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> list[UserResponse]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role,
            must_change_password=u.must_change_password,
        )
        for u in users
    ]
