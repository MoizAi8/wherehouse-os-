"""One-use, user/session/message-bound approval, consumed atomically with DB operations."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from fulfillment.models.chat_approval import ChatApproval


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def issue(db: AsyncSession, session: str, action: str, message: str, payload: dict) -> str:
    token = secrets.token_urlsafe(32)
    db.add(ChatApproval(token_hash=digest(token), session_key=session, action=action,
        message_hash=digest(message), payload_json=json.dumps(payload),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5), consumed=False))
    await db.flush()
    return token


async def consume(db: AsyncSession, token: str, session: str, action: str, message: str) -> dict:
    result = await db.execute(update(ChatApproval).where(
        ChatApproval.token_hash == digest(token), ChatApproval.session_key == session,
        ChatApproval.action == action, ChatApproval.message_hash == digest(message),
        ChatApproval.consumed.is_(False), ChatApproval.expires_at > datetime.now(timezone.utc),
    ).values(consumed=True).returning(ChatApproval.payload_json))
    payload = result.scalar_one_or_none()
    if payload is None:
        raise HTTPException(409, "Confirmation is invalid, expired, already used, or does not match this request")
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise HTTPException(409, "Confirmation payload is invalid")
    return decoded
