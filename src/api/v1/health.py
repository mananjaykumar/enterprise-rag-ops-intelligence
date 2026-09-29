from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.db.session import get_db

router = APIRouter(prefix="/health", tags=["Health & Readiness"])


@router.get(
    "",
    summary="Application & Database Health Probe",
    status_code=status.HTTP_200_OK,
)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Readiness probe used by container orchestrators and load balancers.

    Verifies active connectivity to PostgreSQL + pgvector.
    """
    try:
        result = await db.execute(text("SELECT 1;"))
        if result.scalar() != 1:
            raise ValueError("Database returned unexpected scalar result.")
        db_status = "connected"
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connectivity check failed: {exc}",
        ) from exc

    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "active_embedding_model": settings.ACTIVE_EMBEDDING_MODEL,
    }
