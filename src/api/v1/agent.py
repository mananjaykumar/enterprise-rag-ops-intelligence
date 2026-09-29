from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies import get_current_user
from src.db.models.user import User
from src.db.session import get_db
from src.schemas.agent import AgentQueryRequest, AgentQueryResponse
from src.services.agent_orchestrator import AgentOrchestrator

router = APIRouter(prefix="/agent", tags=["agent"])
agent_orchestrator = AgentOrchestrator()


@router.post(
    "/query",
    status_code=status.HTTP_200_OK,
    response_model=AgentQueryResponse,
)
async def query_enterprise_agent(
    request: AgentQueryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentQueryResponse:
    """Unified intelligence endpoint dispatching single-intent and multi-step hybrid queries."""
    try:
        return await agent_orchestrator.execute_agent(
            db=db,
            user=current_user,
            request=request,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent Execution Failed: {exc}",
        ) from exc
