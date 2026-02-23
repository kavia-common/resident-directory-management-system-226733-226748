from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.config import get_settings
from src.api.core.db import get_db_session

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    email: str
    full_name: Optional[str]
    roles: List[str]


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _hash_matches(password: str, password_hash: str) -> bool:
    # Stored hashes in seed are bcrypt $2b$... strings.
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _create_access_token(user: CurrentUser) -> Dict[str, Any]:
    exp = _now_utc() + timedelta(minutes=settings.jwt_exp_minutes)
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user.id),
        "email": user.email,
        "roles": user.roles,
        "exp": exp,
        "iat": _now_utc(),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return {"token": token, "exp": exp}


# PUBLIC_INTERFACE
async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[CurrentUser]:
    """Authenticate a user by email/password against the users table."""
    row = (
        await db.execute(
            text(
                """
                SELECT id, email, full_name, password_hash, is_active
                FROM users
                WHERE email = :email
                """
            ),
            {"email": email},
        )
    ).mappings().first()

    if not row or not row["is_active"]:
        return None

    if not _hash_matches(password, row["password_hash"]):
        return None

    roles_rows = (
        await db.execute(
            text(
                """
                SELECT r.name
                FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                WHERE ur.user_id = :uid
                """
            ),
            {"uid": row["id"]},
        )
    ).mappings().all()
    roles = [r["name"] for r in roles_rows]

    return CurrentUser(
        id=int(row["id"]),
        email=row["email"],
        full_name=row["full_name"],
        roles=roles,
    )


async def _get_user_from_token(db: AsyncSession, token: str) -> CurrentUser:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = int(payload.get("sub"))
    roles = payload.get("roles") or []

    # Ensure user is still active in DB.
    row = (
        await db.execute(
            text("SELECT id, email, full_name, is_active FROM users WHERE id = :id"),
            {"id": user_id},
        )
    ).mappings().first()
    if not row or not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    return CurrentUser(
        id=int(row["id"]),
        email=row["email"],
        full_name=row["full_name"],
        roles=list(roles),
    )


# PUBLIC_INTERFACE
async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """FastAPI dependency to get current user from Authorization: Bearer token."""
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return await _get_user_from_token(db, creds.credentials)


# PUBLIC_INTERFACE
def require_roles(required: List[str]):
    """Dependency factory enforcing that the current user has at least one required role."""

    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(user.roles).intersection(set(required)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Requires one of: {required}",
            )
        return user

    return _dep


# PUBLIC_INTERFACE
def issue_token_for_user(user: CurrentUser) -> Dict[str, Any]:
    """Issue a signed JWT for a given CurrentUser."""
    return _create_access_token(user)
