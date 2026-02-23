from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.auth import CurrentUser


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


# PUBLIC_INTERFACE
async def write_audit_log(
    db: AsyncSession,
    *,
    actor: Optional[CurrentUser],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Write an audit log entry.

    This is intentionally low-level and uses raw SQL to match the existing DB schema.
    """
    await db.execute(
        text(
            """
            INSERT INTO audit_log (
                actor_user_id, actor_email, action, entity_type, entity_id, before, after, metadata, created_at
            )
            VALUES (
                :actor_user_id, :actor_email, :action, :entity_type, :entity_id, :before::jsonb, :after::jsonb, :metadata::jsonb, :created_at
            )
            """
        ),
        {
            "actor_user_id": actor.id if actor else None,
            "actor_email": actor.email if actor else None,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "before": None if before is None else __import__("json").dumps(before),
            "after": None if after is None else __import__("json").dumps(after),
            "metadata": None if metadata is None else __import__("json").dumps(metadata),
            "created_at": _now_utc(),
        },
    )
