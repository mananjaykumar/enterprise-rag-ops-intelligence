from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies import get_current_user
from src.db.models.operational import SqlQueryAuditLog
from src.db.models.user import User
from src.db.session import get_db
from src.schemas.sql import (
    NaturalLanguageSQLRequest,
    SQLAuditLogResponse,
    SQLQueryResult,
)
from src.services.sql_sandbox import SQLSecurityViolation
from src.services.text_to_sql import TextToSQLService

router = APIRouter(prefix="/sql", tags=["sql"])
text_to_sql_service = TextToSQLService()


@router.post(
    "/query",
    status_code=status.HTTP_200_OK,
    response_model=SQLQueryResult,
)
async def execute_natural_language_sql(
    request: NaturalLanguageSQLRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SQLQueryResult:
    """Translates natural language to SQL, validates via 5-gate sandbox, and returns tabular data."""
    try:
        return await text_to_sql_service.execute_query(
            db=db,
            user=current_user,
            request=request,
        )
    except SQLSecurityViolation as sec_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security Sandbox Violation: {sec_err}",
        ) from sec_err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL Query Execution Failed: {exc}",
        ) from exc


@router.get(
    "/audit-logs",
    response_model=list[SQLAuditLogResponse],
)
async def get_sql_audit_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[SQLAuditLogResponse]:
    """Retrieves immutable audit logs for the current tenant's SQL queries."""
    stmt = (
        select(SqlQueryAuditLog)
        .where(SqlQueryAuditLog.tenant_id == current_user.tenant_id)
        .order_by(desc(SqlQueryAuditLog.created_at))
        .limit(min(limit, 100))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
