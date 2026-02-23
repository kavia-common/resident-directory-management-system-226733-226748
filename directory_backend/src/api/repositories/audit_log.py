from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _row_to_audit(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(row["id"]),
        "actor_user_id": row["actor_user_id"],
        "actor_email": row["actor_email"],
        "action": row["action"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "before": row["before"],
        "after": row["after"],
        "metadata": row["metadata"],
        "created_at": row["created_at"],
    }


# PUBLIC_INTERFACE
async def list_audit_log(
    db: AsyncSession,
    *,
    action: Optional[str],
    actor_email: Optional[str],
    entity_type: Optional[str],
    limit: int,
    offset: int,
) -> Tuple[List[Dict[str, Any]], int]:
    """List audit log entries with basic filtering."""
    where = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if action:
        where.append("action = :action")
        params["action"] = action
    if actor_email:
        where.append("actor_email ILIKE :actor_email")
        params["actor_email"] = f"%{actor_email}%"
    if entity_type:
        where.append("entity_type = :entity_type")
        params["entity_type"] = entity_type

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total_row = (
        await db.execute(text(f"SELECT COUNT(*) AS c FROM audit_log {where_sql}"), params)
    ).mappings().first()
    total = int(total_row["c"]) if total_row else 0

    rows = (
        await db.execute(
            text(
                f"""
                SELECT *
                FROM audit_log
                {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()

    return ([_row_to_audit(dict(r)) for r in rows], total)
