import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.core.config import get_settings
from src.api.routes.audit import router as audit_router
from src.api.routes.auth import router as auth_router
from src.api.routes.residents import router as residents_router

settings = get_settings()

openapi_tags = [
    {"name": "auth", "description": "Authentication endpoints (JWT)."},
    {"name": "residents", "description": "Residents directory CRUD, search, CSV import/export, photo upload."},
    {"name": "audit", "description": "Audit log listing."},
    {"name": "meta", "description": "Health and documentation helper endpoints."},
]

app = FastAPI(
    title="Resident Directory Backend API",
    description=(
        "FastAPI backend for resident directory management.\n\n"
        "Auth: obtain a JWT via POST /auth/login, then call protected endpoints with "
        "`Authorization: Bearer <token>`.\n\n"
        "Roles:\n"
        "- admin: full access\n"
        "- viewer: read-only\n"
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

# CORS aligned with .env ALLOWED_ORIGINS / methods / headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=settings.allowed_methods,
    allow_headers=settings.allowed_headers,
    max_age=settings.cors_max_age,
)

# Serve uploaded photos
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(auth_router)
app.include_router(residents_router)
app.include_router(audit_router)


@app.get(
    "/",
    tags=["meta"],
    summary="Health check",
    operation_id="health_check",
)
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}
