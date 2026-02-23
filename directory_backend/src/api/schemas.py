from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Token expiry in seconds")
    user: Dict[str, Any] = Field(..., description="Basic user info, including roles")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class ResidentBase(BaseModel):
    full_name: str = Field(..., description="Resident full name")
    unit: str = Field(..., description="Unit/apartment identifier")
    building: Optional[str] = Field(None, description="Building identifier")
    floor: Optional[str] = Field(None, description="Floor identifier")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    notes: Optional[str] = Field(None, description="Freeform notes")


class ResidentCreate(ResidentBase):
    is_active: bool = Field(True, description="Whether resident is active")


class ResidentUpdate(BaseModel):
    full_name: Optional[str] = Field(None, description="Resident full name")
    unit: Optional[str] = Field(None, description="Unit/apartment identifier")
    building: Optional[str] = Field(None, description="Building identifier")
    floor: Optional[str] = Field(None, description="Floor identifier")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    notes: Optional[str] = Field(None, description="Freeform notes")
    is_active: Optional[bool] = Field(None, description="Whether resident is active")


class ResidentOut(ResidentBase):
    id: int = Field(..., description="Resident ID")
    photo_url: Optional[str] = Field(None, description="Public URL to resident photo")
    is_active: bool = Field(..., description="Whether resident is active")
    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: datetime = Field(..., description="Updated timestamp")
    deactivated_at: Optional[datetime] = Field(None, description="Deactivated timestamp (if inactive)")


class ResidentListResponse(BaseModel):
    items: List[ResidentOut] = Field(..., description="Residents on this page")
    total: int = Field(..., description="Total number of matching residents")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Offset into result set")


class AuditLogOut(BaseModel):
    id: int = Field(..., description="Audit log entry ID")
    actor_user_id: Optional[int] = Field(None, description="Actor user id (nullable)")
    actor_email: Optional[str] = Field(None, description="Actor email (nullable)")
    action: str = Field(..., description="Action name (e.g., CREATE_RESIDENT)")
    entity_type: Optional[str] = Field(None, description="Entity type (e.g., resident)")
    entity_id: Optional[str] = Field(None, description="Entity id as string")
    before: Optional[Dict[str, Any]] = Field(None, description="JSON before state")
    after: Optional[Dict[str, Any]] = Field(None, description="JSON after state")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: datetime = Field(..., description="Created timestamp")


class CsvImportResult(BaseModel):
    created: int = Field(..., description="Number of residents created")
    updated: int = Field(..., description="Number of residents updated")
    skipped: int = Field(..., description="Number of rows skipped due to validation errors")
    errors: List[str] = Field(default_factory=list, description="Row-level error messages")
