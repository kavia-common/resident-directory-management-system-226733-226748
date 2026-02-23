import os
from dataclasses import dataclass
from typing import List, Optional


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    # CORS
    allowed_origins: List[str]
    allowed_methods: List[str]
    allowed_headers: List[str]
    cors_max_age: int

    # Auth / JWT
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    jwt_exp_minutes: int

    # Database (Postgres)
    postgres_url: str

    # Uploads
    upload_dir: str
    public_base_url: str


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Load settings from environment variables.

    Environment variables required:
    - POSTGRES_URL (preferred) OR DATABASE_URL (fallback)
    - JWT_SECRET
    Optional:
    - ALLOWED_ORIGINS, ALLOWED_METHODS, ALLOWED_HEADERS, CORS_MAX_AGE
    - JWT_ISSUER, JWT_AUDIENCE, JWT_EXP_MINUTES
    - UPLOAD_DIR, PUBLIC_BASE_URL
    """
    postgres_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if not postgres_url:
        # Do not hardcode; fail fast with actionable error.
        raise RuntimeError(
            "Missing POSTGRES_URL (or DATABASE_URL) environment variable for Postgres connection."
        )

    jwt_secret = os.getenv("JWT_SECRET")
    if not jwt_secret:
        raise RuntimeError("Missing JWT_SECRET environment variable for JWT signing.")

    allowed_origins = _split_csv(os.getenv("ALLOWED_ORIGINS")) or ["*"]
    allowed_methods = _split_csv(os.getenv("ALLOWED_METHODS")) or ["*"]
    allowed_headers = _split_csv(os.getenv("ALLOWED_HEADERS")) or ["*"]

    cors_max_age = int(os.getenv("CORS_MAX_AGE") or "3600")

    jwt_issuer = os.getenv("JWT_ISSUER") or "resident-directory-backend"
    jwt_audience = os.getenv("JWT_AUDIENCE") or "resident-directory-frontend"
    jwt_exp_minutes = int(os.getenv("JWT_EXP_MINUTES") or "480")

    upload_dir = os.getenv("UPLOAD_DIR") or "uploads"
    public_base_url = os.getenv("PUBLIC_BASE_URL") or (os.getenv("BACKEND_URL") or "")

    return Settings(
        allowed_origins=allowed_origins,
        allowed_methods=allowed_methods,
        allowed_headers=allowed_headers,
        cors_max_age=cors_max_age,
        jwt_secret=jwt_secret,
        jwt_issuer=jwt_issuer,
        jwt_audience=jwt_audience,
        jwt_exp_minutes=jwt_exp_minutes,
        postgres_url=postgres_url,
        upload_dir=upload_dir,
        public_base_url=public_base_url.rstrip("/"),
    )
