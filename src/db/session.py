from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import get_settings

settings = get_settings()

# 1. Initialize Async Engine with connection pooling
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Proactively pings connection to drop stale connections
)

# 2. Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# 3. FastAPI Dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async SQLAlchemy session.

    Guarantees session cleanup upon request completion.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
