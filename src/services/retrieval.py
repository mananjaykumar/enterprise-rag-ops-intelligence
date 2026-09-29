import logging
import uuid
from typing import Any

from sqlalchemy import any_, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import get_settings
from src.db.models.document import Document, DocumentChunk
from src.db.models.user import User, UserRole
from src.domain.interfaces.embedding import BaseEmbeddingClient
from src.domain.interfaces.rerank import BaseRerankClient
from src.infrastructure.ai.flashrank import FlashRankClient
from src.infrastructure.ai.gemini import GeminiEmbeddingClient
from src.schemas.retrieval import CitationSource, RetrievedChunk

logger = logging.getLogger(__name__)
settings = get_settings()


class RetrievalService:
    """Production Two-Tier Hybrid Retrieval Service with security pre-filters, RRF, and FlashRank."""

    def __init__(
        self,
        embedding_client: BaseEmbeddingClient | None = None,
        rerank_client: BaseRerankClient | None = None,
    ) -> None:
        self.embedding_client = embedding_client or GeminiEmbeddingClient()
        self.rerank_client = rerank_client or FlashRankClient()

    def _build_security_conditions(self, user: User) -> list[Any]:
        """Constructs hard SQL pre-filters ensuring zero tenant or RBAC data leakage."""
        conditions = [
            DocumentChunk.tenant_id == user.tenant_id,
            DocumentChunk.is_active.is_(True),
            DocumentChunk.embedding_model == settings.ACTIVE_EMBEDDING_MODEL,
        ]
        # Admins can read all documents in their tenant; other roles must match allowed_roles
        if user.role != UserRole.ADMIN:
            conditions.append(literal(user.role.value) == any_(DocumentChunk.allowed_roles))

        return conditions

    async def _dense_search(
        self,
        db: AsyncSession,
        user: User,
        query_vector: list[float],
        top_k: int,
    ) -> list[DocumentChunk]:
        """Executes pgvector cosine distance nearest-neighbor search with security pre-filter."""
        conditions = self._build_security_conditions(user)
        distance_col = DocumentChunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(DocumentChunk)
            .options(selectinload(DocumentChunk.document))
            .where(*conditions)
            .order_by(distance_col.asc())
            .limit(top_k)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _sparse_search(
        self,
        db: AsyncSession,
        user: User,
        query_text: str,
        top_k: int,
    ) -> list[DocumentChunk]:
        """Executes PostgreSQL Full-Text Search against fts_tokens with security pre-filter."""
        conditions = self._build_security_conditions(user)
        tsquery = func.plainto_tsquery("english", query_text)
        fts_match = DocumentChunk.fts_tokens.op("@@")(tsquery)
        rank_col = func.ts_rank_cd(DocumentChunk.fts_tokens, tsquery)

        stmt = (
            select(DocumentChunk)
            .options(selectinload(DocumentChunk.document))
            .where(*conditions, fts_match)
            .order_by(rank_col.desc())
            .limit(top_k)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _reciprocal_rank_fusion(
        self,
        dense_results: list[DocumentChunk],
        sparse_results: list[DocumentChunk],
        k: int = 60,
    ) -> list[dict[str, Any]]:
        """Merges two ranked candidate lists using standard RRF (1 / (k + rank))."""
        fused_scores: dict[uuid.UUID, dict[str, Any]] = {}

        # 1. Process Dense Ranks
        for rank_0, chunk in enumerate(dense_results):
            rank = rank_0 + 1
            score = 1.0 / (k + rank)
            if chunk.id not in fused_scores:
                fused_scores[chunk.id] = {
                    "chunk": chunk,
                    "dense_rank": rank,
                    "sparse_rank": None,
                    "rrf_score": score,
                }
            else:
                fused_scores[chunk.id]["dense_rank"] = rank
                fused_scores[chunk.id]["rrf_score"] += score

        # 2. Process Sparse Ranks
        for rank_0, chunk in enumerate(sparse_results):
            rank = rank_0 + 1
            score = 1.0 / (k + rank)
            if chunk.id not in fused_scores:
                fused_scores[chunk.id] = {
                    "chunk": chunk,
                    "dense_rank": None,
                    "sparse_rank": rank,
                    "rrf_score": score,
                }
            else:
                fused_scores[chunk.id]["sparse_rank"] = rank
                fused_scores[chunk.id]["rrf_score"] += score

        # Sort descending by cumulative RRF score
        ranked_items = sorted(
            fused_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )
        return ranked_items

    def _reorder_lost_in_the_middle(
        self,
        items: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """Distributes high-relevance items to the beginning and end of the context window.

        Avoids cognitive degradation in LLMs when relevant facts are placed in the middle.
        """
        if len(items) <= 2:
            return items

        reordered: list[RetrievedChunk] = []
        left = True
        for item in items:
            if left:
                reordered.insert(0, item)
            else:
                reordered.append(item)
            left = not left

        # Reverse so that top #1 is at the very beginning
        return reordered[::-1]

    async def search(
        self,
        db: AsyncSession,
        user: User,
        query: str,
        top_k: int = 20,
        top_n: int = 5,
        score_threshold: float = 0.0,
        max_tokens: int = 4000,
    ) -> list[RetrievedChunk]:
        """Orchestrates hybrid retrieval: Embedding -> Dense+Sparse -> RRF -> FlashRank -> Reordering."""
        # 1. Generate query embedding
        query_vector = await self.embedding_client.embed_query(query)

        # 2. Parallel candidate retrieval
        dense_results = await self._dense_search(db, user, query_vector, top_k=top_k)
        sparse_results = await self._sparse_search(db, user, query, top_k=top_k)

        if not dense_results and not sparse_results:
            return []

        # 3. Reciprocal Rank Fusion
        fused_candidates = self._reciprocal_rank_fusion(dense_results, sparse_results, k=60)

        # 4. Prepare passages for Cross-Encoder Reranker
        passages_for_rerank = [
            {
                "id": str(item["chunk"].id),
                "text": item["chunk"].content,
                "metadata": item,
            }
            for item in fused_candidates
        ]

        # 5. Rerank using local FlashRank
        reranked_passages = await self.rerank_client.rerank(
            query=query,
            passages=passages_for_rerank,
            top_n=top_n * 2,  # Fetch extra for soft threshold & budget pruning
        )

        # 6. Apply score threshold & build RetrievedChunk models
        retrieved: list[RetrievedChunk] = []
        token_count = 0

        for p in reranked_passages:
            score = float(p.get("score", 0.0))
            if score < score_threshold:
                continue

            # Approximate tokens (~4 characters per token)
            text_len = len(p["text"])
            est_tokens = max(1, text_len // 4)
            if token_count + est_tokens > max_tokens and retrieved:
                break
            token_count += est_tokens

            meta = p["metadata"]
            chunk: DocumentChunk = meta["chunk"]
            doc: Document = chunk.document

            retrieved.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    content=chunk.content,
                    source=CitationSource(
                        document_id=chunk.document_id,
                        document_title=doc.title if doc else None,
                        filename=doc.filename if doc else "unknown",
                        chunk_index=chunk.chunk_index,
                        page_number=chunk.page_number,
                        section_heading=chunk.section_heading,
                        heading_hierarchy=chunk.heading_hierarchy or [],
                        chunk_type=chunk.chunk_type,
                    ),
                    dense_rank=meta["dense_rank"],
                    sparse_rank=meta["sparse_rank"],
                    rrf_score=meta["rrf_score"],
                    rerank_score=score,
                )
            )
            if len(retrieved) >= top_n:
                break

        # 7. Apply Lost-in-the-Middle edge distribution
        return self._reorder_lost_in_the_middle(retrieved)
