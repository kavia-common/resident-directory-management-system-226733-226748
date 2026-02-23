from __future__ import annotations

import csv
import io
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.audit import write_audit_log
from src.api.core.auth import CurrentUser, require_roles
from src.api.core.config import get_settings
from src.api.core.db import get_db_session
from src.api.repositories.residents import (
    create_resident,
    get_resident,
    list_residents,
    set_resident_photo_url,
    update_resident,
)
from src.api.schemas import CsvImportResult, ResidentCreate, ResidentListResponse, ResidentOut, ResidentUpdate

router = APIRouter(prefix="/residents", tags=["residents"])
settings = get_settings()


def _public_photo_url(filename: str) -> str:
    # Expose via /uploads/{filename}
    base = settings.public_base_url
    if not base:
        return f"/uploads/{filename}"
    return f"{base}/uploads/{filename}"


@router.get(
    "",
    response_model=ResidentListResponse,
    summary="List residents with search and filters",
    description="Supports q (search), building/floor/unit filters, is_active, and pagination.",
    operation_id="residents_list",
)
async def residents_list(
    q: Optional[str] = Query(None, description="Search string across name/unit/email/phone"),
    building: Optional[str] = Query(None, description="Filter by building"),
    floor: Optional[str] = Query(None, description="Filter by floor"),
    unit: Optional[str] = Query(None, description="Filter by unit"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset"),
    db: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles(["admin", "viewer"])),
) -> ResidentListResponse:
    """List residents (RBAC: admin/viewer)."""
    items, total = await list_residents(
        db,
        q=q,
        building=building,
        floor=floor,
        unit=unit,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return ResidentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{resident_id}",
    response_model=ResidentOut,
    summary="Get resident by id",
    operation_id="residents_get",
)
async def residents_get(
    resident_id: int,
    db: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles(["admin", "viewer"])),
) -> ResidentOut:
    """Get a resident by id (RBAC: admin/viewer)."""
    resident = await get_resident(db, resident_id)
    if not resident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")
    return resident


@router.post(
    "",
    response_model=ResidentOut,
    summary="Create resident",
    operation_id="residents_create",
)
async def residents_create(
    payload: ResidentCreate,
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(require_roles(["admin"])),
) -> ResidentOut:
    """Create a resident (RBAC: admin)."""
    created = await create_resident(
        db,
        {
            "full_name": payload.full_name,
            "unit": payload.unit,
            "building": payload.building,
            "floor": payload.floor,
            "phone": payload.phone,
            "email": payload.email,
            "photo_url": None,
            "notes": payload.notes,
            "is_active": payload.is_active,
        },
    )
    await write_audit_log(
        db,
        actor=user,
        action="CREATE_RESIDENT",
        entity_type="resident",
        entity_id=str(created["id"]),
        before=None,
        after=created,
    )
    await db.commit()
    return created


@router.put(
    "/{resident_id}",
    response_model=ResidentOut,
    summary="Update resident",
    operation_id="residents_update",
)
async def residents_update(
    resident_id: int,
    payload: ResidentUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(require_roles(["admin"])),
) -> ResidentOut:
    """Update a resident (RBAC: admin)."""
    before = await get_resident(db, resident_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")

    patch = payload.model_dump(exclude_unset=True)
    updated = await update_resident(db, resident_id, patch)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")

    await write_audit_log(
        db,
        actor=user,
        action="UPDATE_RESIDENT",
        entity_type="resident",
        entity_id=str(resident_id),
        before=before,
        after=updated,
    )
    await db.commit()
    return updated


@router.patch(
    "/{resident_id}/deactivate",
    response_model=ResidentOut,
    summary="Deactivate resident",
    operation_id="residents_deactivate",
)
async def residents_deactivate(
    resident_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(require_roles(["admin"])),
) -> ResidentOut:
    """Deactivate a resident (RBAC: admin)."""
    before = await get_resident(db, resident_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")

    updated = await update_resident(db, resident_id, {"is_active": False})
    await write_audit_log(
        db,
        actor=user,
        action="DEACTIVATE_RESIDENT",
        entity_type="resident",
        entity_id=str(resident_id),
        before=before,
        after=updated,
    )
    await db.commit()
    return updated


@router.post(
    "/{resident_id}/photo",
    response_model=ResidentOut,
    summary="Upload resident photo",
    description="Uploads a photo for a resident and sets photo_url. RBAC: admin.",
    operation_id="residents_upload_photo",
)
async def upload_photo(
    resident_id: int,
    photo: UploadFile = File(..., description="Image file"),
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(require_roles(["admin"])),
) -> ResidentOut:
    """Upload a resident photo (RBAC: admin)."""
    before = await get_resident(db, resident_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")

    os.makedirs(settings.upload_dir, exist_ok=True)

    # Keep simple deterministic filename; in production prefer UUID.
    ext = os.path.splitext(photo.filename or "")[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ""]:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    filename = f"resident_{resident_id}{ext or '.jpg'}"
    path = os.path.join(settings.upload_dir, filename)

    content = await photo.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    with open(path, "wb") as f:
        f.write(content)

    photo_url = _public_photo_url(filename)
    updated = await set_resident_photo_url(db, resident_id, photo_url)

    await write_audit_log(
        db,
        actor=user,
        action="UPLOAD_RESIDENT_PHOTO",
        entity_type="resident",
        entity_id=str(resident_id),
        before=before,
        after=updated,
        metadata={"filename": filename},
    )
    await db.commit()
    return updated


@router.get(
    "/export.csv",
    summary="Export residents to CSV",
    description="Exports residents (optionally filtered) as CSV. RBAC: admin.",
    operation_id="residents_export_csv",
)
async def export_csv(
    q: Optional[str] = Query(None),
    building: Optional[str] = Query(None),
    floor: Optional[str] = Query(None),
    unit: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(require_roles(["admin"])),
) -> Response:
    """Export residents as CSV (RBAC: admin)."""
    items, _total = await list_residents(
        db,
        q=q,
        building=building,
        floor=floor,
        unit=unit,
        is_active=is_active,
        limit=100000,
        offset=0,
    )

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "id",
            "full_name",
            "unit",
            "building",
            "floor",
            "phone",
            "email",
            "photo_url",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
            "deactivated_at",
        ],
    )
    writer.writeheader()
    for r in items:
        writer.writerow(r)

    await write_audit_log(
        db,
        actor=user,
        action="EXPORT_CSV",
        entity_type="resident",
        entity_id=None,
        metadata={"filters": {"q": q, "building": building, "floor": floor, "unit": unit, "is_active": is_active}},
    )
    await db.commit()

    data = buf.getvalue().encode("utf-8")
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=residents.csv"},
    )


@router.post(
    "/import.csv",
    response_model=CsvImportResult,
    summary="Import residents from CSV",
    description="CSV columns: full_name, unit, building, floor, phone, email, notes, is_active. If id provided, updates that resident.",
    operation_id="residents_import_csv",
)
async def import_csv(
    file: UploadFile = File(..., description="CSV file"),
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(require_roles(["admin"])),
) -> CsvImportResult:
    """Import residents from CSV (RBAC: admin)."""
    content = await file.read()
    try:
        text_data = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text_data))
    created = updated = skipped = 0
    errors = []

    for idx, row in enumerate(reader, start=2):  # header is line 1
        try:
            full_name = (row.get("full_name") or "").strip()
            unit = (row.get("unit") or "").strip()
            if not full_name or not unit:
                raise ValueError("full_name and unit are required")

            patch = {
                "full_name": full_name,
                "unit": unit,
                "building": (row.get("building") or "").strip() or None,
                "floor": (row.get("floor") or "").strip() or None,
                "phone": (row.get("phone") or "").strip() or None,
                "email": (row.get("email") or "").strip() or None,
                "notes": (row.get("notes") or "").strip() or None,
            }

            is_active_raw = row.get("is_active")
            if is_active_raw is not None and str(is_active_raw).strip() != "":
                patch["is_active"] = str(is_active_raw).strip().lower() in ["1", "true", "yes", "y"]

            id_raw = (row.get("id") or "").strip()
            if id_raw:
                resident_id = int(id_raw)
                before = await get_resident(db, resident_id)
                if not before:
                    raise ValueError(f"id={resident_id} not found for update")
                after = await update_resident(db, resident_id, patch)
                updated += 1
                await write_audit_log(
                    db,
                    actor=user,
                    action="IMPORT_UPDATE_RESIDENT",
                    entity_type="resident",
                    entity_id=str(resident_id),
                    before=before,
                    after=after,
                    metadata={"row": idx},
                )
            else:
                after = await create_resident(
                    db,
                    {
                        **patch,
                        "photo_url": None,
                        "is_active": patch.get("is_active", True),
                    },
                )
                created += 1
                await write_audit_log(
                    db,
                    actor=user,
                    action="IMPORT_CREATE_RESIDENT",
                    entity_type="resident",
                    entity_id=str(after["id"]),
                    before=None,
                    after=after,
                    metadata={"row": idx},
                )

        except Exception as e:  # noqa: BLE001 (intentional: row-level error capture)
            skipped += 1
            errors.append(f"Line {idx}: {e}")

    await write_audit_log(
        db,
        actor=user,
        action="IMPORT_CSV",
        entity_type="resident",
        entity_id=None,
        metadata={"created": created, "updated": updated, "skipped": skipped},
    )
    await db.commit()

    return CsvImportResult(created=created, updated=updated, skipped=skipped, errors=errors)
