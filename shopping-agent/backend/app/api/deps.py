"""
Shared FastAPI dependencies used across all routes.
"""
from fastapi import Header, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Returns current user if authenticated, None for guest users.
    Use this for routes that work for both guests and logged-in users.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split(" ")[1]
        payload = decode_access_token(token)
        if not payload:
            return None
        user_id = int(payload.get("sub", 0))
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return None


async def get_required_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Returns current user. Raises 401 if not authenticated.
    Use this for routes that require login.
    """
    user = await get_optional_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
