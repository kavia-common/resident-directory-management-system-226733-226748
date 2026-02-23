from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.audit import write_audit_log
from src.api.core.auth import authenticate_user, issue_token_for_user
from src.api.core.db import get_db_session
from src.api.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login (basic auth) and receive a JWT",
    description="Authenticates a user by email/password and returns a JWT access token.",
    operation_id="auth_login",
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db_session)) -> TokenResponse:
    """Authenticate user credentials and return a JWT."""
    user = await authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # update last_login_at
    await db.execute(
        text("UPDATE users SET last_login_at = NOW() WHERE id = :id"),
        {"id": user.id},
    )
    await write_audit_log(
        db,
        actor=user,
        action="LOGIN",
        entity_type="user",
        entity_id=str(user.id),
        metadata={"email": user.email},
    )
    await db.commit()

    token_info = issue_token_for_user(user)
    expires_in = int((token_info["exp"] - __import__("datetime").datetime.now(__import__("datetime").timezone.utc)).total_seconds())

    return TokenResponse(
        access_token=token_info["token"],
        token_type="bearer",
        expires_in=expires_in,
        user={"id": user.id, "email": user.email, "full_name": user.full_name, "roles": user.roles},
    )
