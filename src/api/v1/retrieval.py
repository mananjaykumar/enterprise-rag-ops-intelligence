from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies import get_current_user
from src.db.models.user import User
from src.db.session import get_db
from src.schemas.retrieval import SearchRequest, SearchResponse
from src.services.retrieval import RetrievalService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])
retrieval_service = RetrievalService()


@router.post(
    "/search",
    status_code=status.HTTP_200_OK,
    response_model=SearchResponse,
)
async def hybrid_search(
    request: SearchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SearchResponse:
    """Executes authenticated two-tier hybrid search with pre-retrieval RBAC security."""
    results = await retrieval_service.search(
        db=db,
        user=current_user,
        query=request.query,
        top_k=request.top_k,
        top_n=request.top_n,
        score_threshold=request.score_threshold,
        max_tokens=request.max_tokens,
    )

    return SearchResponse(
        query=request.query,
        total_candidates=len(results),
        returned_count=len(results),
        results=results,
    )
