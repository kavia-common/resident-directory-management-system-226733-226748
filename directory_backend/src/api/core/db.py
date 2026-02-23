from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.core.config import get_settings

settings = get_settings()

# Convert sync-style URL to async driver if needed.
# Expected format from resident_db: postgresql://user:pass@host:port/db
if settings.postgres_url.startswith("postgresql://"):
    async_database_url = settings.postgres_url.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
elif settings.postgres_url.startswith("postgresql+asyncpg://"):
    async_database_url = settings.postgres_url
else:
    # Fail fast to avoid mysterious driver errors.
    raise RuntimeError(
        "Unsupported POSTGRES_URL scheme. Expected postgresql://... or postgresql+asyncpg://..."
    )

engine = create_async_engine(async_database_url, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# PUBLIC_INTERFACE
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
