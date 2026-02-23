from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.auth import CurrentUser, require_roles
from src.api.core.db import get_db_session
from src.api.repositories.audit_log import list_audit_log


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "",
    response_model=dict,
    summary="List audit log entries",
    description="RBAC: viewer/admin. Returns {items, total, limit, offset}.",
    operation_id="audit_list",
)
async def audit_list(
    action: Optional[str] = Query(None, description="Filter by action"),
    actor_email: Optional[str] = Query(None, description="Filter by actor email substring"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles(["admin", "viewer"])),
) -> dict:
    """List audit log entries."""
    items, total = await list_audit_log(
        db, action=action, actor_email=actor_email, entity_type=entity_type, limit=limit, offset=offset
    )
    # Explicit cast to AuditLogOut models not necessary; FastAPI will validate output.
    return {"items": items, "total": total, "limit": limit, "offset": offset}
