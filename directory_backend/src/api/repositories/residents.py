from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _row_to_resident(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(row["id"]),
        "full_name": row["full_name"],
        "unit": row["unit"],
        "building": row["building"],
        "floor": row["floor"],
        "phone": row["phone"],
        "email": row["email"],
        "photo_url": row["photo_url"],
        "notes": row["notes"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "deactivated_at": row["deactivated_at"],
    }


# PUBLIC_INTERFACE
async def get_resident(db: AsyncSession, resident_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a resident by id."""
    row = (
        await db.execute(
            text(
                """
                SELECT *
                FROM residents
                WHERE id = :id
                """
            ),
            {"id": resident_id},
        )
    ).mappings().first()
    if not row:
        return None
    return _row_to_resident(dict(row))


# PUBLIC_INTERFACE
async def list_residents(
    db: AsyncSession,
    *,
    q: Optional[str],
    building: Optional[str],
    floor: Optional[str],
    unit: Optional[str],
    is_active: Optional[bool],
    limit: int,
    offset: int,
) -> Tuple[List[Dict[str, Any]], int]:
    """List residents with optional search/filter and pagination."""
    where = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if q:
        # Basic ILIKE search across name/unit/email/phone
        where.append(
            "(full_name ILIKE :q OR unit ILIKE :q OR COALESCE(email,'') ILIKE :q OR COALESCE(phone,'') ILIKE :q)"
        )
        params["q"] = f"%{q}%"
    if building:
        where.append("building = :building")
        params["building"] = building
    if floor:
        where.append("floor = :floor")
        params["floor"] = floor
    if unit:
        where.append("unit = :unit")
        params["unit"] = unit
    if is_active is not None:
        where.append("is_active = :is_active")
        params["is_active"] = is_active

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total_row = (
        await db.execute(text(f"SELECT COUNT(*) AS c FROM residents {where_sql}"), params)
    ).mappings().first()
    total = int(total_row["c"]) if total_row else 0

    rows = (
        await db.execute(
            text(
                f"""
                SELECT *
                FROM residents
                {where_sql}
                ORDER BY is_active DESC, building NULLS LAST, floor NULLS LAST, unit NULLS LAST, full_name ASC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()

    return ([_row_to_resident(dict(r)) for r in rows], total)


# PUBLIC_INTERFACE
async def create_resident(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a resident and return row."""
    row = (
        await db.execute(
            text(
                """
                INSERT INTO residents (full_name, unit, building, floor, phone, email, photo_url, notes, is_active)
                VALUES (:full_name, :unit, :building, :floor, :phone, :email, :photo_url, :notes, :is_active)
                RETURNING *
                """
            ),
            data,
        )
    ).mappings().first()
    return _row_to_resident(dict(row))


# PUBLIC_INTERFACE
async def update_resident(
    db: AsyncSession, resident_id: int, patch: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Update resident with a patch dict. Returns updated resident or None if not found."""
    if not patch:
        return await get_resident(db, resident_id)

    # Build dynamic SET list
    set_clauses = []
    params: Dict[str, Any] = {"id": resident_id}
    for key, value in patch.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = value

    set_sql = ", ".join(set_clauses)

    row = (
        await db.execute(
            text(
                f"""
                UPDATE residents
                SET {set_sql},
                    deactivated_at = CASE
                        WHEN :is_active_present = TRUE AND :new_is_active = FALSE THEN NOW()
                        WHEN :is_active_present = TRUE AND :new_is_active = TRUE THEN NULL
                        ELSE deactivated_at
                    END
                WHERE id = :id
                RETURNING *
                """
            ),
            {
                **params,
                "is_active_present": "is_active" in patch,
                "new_is_active": patch.get("is_active", True),
            },
        )
    ).mappings().first()

    if not row:
        return None
    return _row_to_resident(dict(row))


# PUBLIC_INTERFACE
async def set_resident_photo_url(
    db: AsyncSession, resident_id: int, photo_url: str
) -> Optional[Dict[str, Any]]:
    """Update a resident photo_url."""
    row = (
        await db.execute(
            text(
                """
                UPDATE residents
                SET photo_url = :photo_url
                WHERE id = :id
                RETURNING *
                """
            ),
            {"id": resident_id, "photo_url": photo_url},
        )
    ).mappings().first()
    if not row:
        return None
    return _row_to_resident(dict(row))
