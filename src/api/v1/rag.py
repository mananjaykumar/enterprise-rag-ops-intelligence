from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies import get_current_user
from src.db.models.user import User
from src.db.session import get_db
from src.schemas.rag import RAGQueryRequest, RAGQueryResponse
from src.services.rag import RAGService

router = APIRouter(prefix="/rag", tags=["rag"])
rag_service = RAGService()


@router.post(
    "/ask",
    status_code=status.HTTP_200_OK,
    response_model=RAGQueryResponse,
)
async def ask_question(
    request: RAGQueryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RAGQueryResponse:
    """Answers user queries strictly grounded in accessible enterprise documents with citations."""
    return await rag_service.answer(
        db=db,
        user=current_user,
        request=request,
    )


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
)
async def stream_question(
    request: RAGQueryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Streams real-time tokens via SSE (text/event-stream) terminating with citation metadata."""
    return StreamingResponse(
        rag_service.stream_answer(db=db, user=current_user, request=request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
