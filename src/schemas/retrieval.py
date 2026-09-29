import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000, description="Search query or question")
    top_k: int = Field(
        default=20, ge=1, le=100, description="Candidate pool size per retrieval leg"
    )
    top_n: int = Field(default=5, ge=1, le=50, description="Final number of reranked chunks")
    score_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum rerank score filter"
    )
    max_tokens: int = Field(
        default=4000, ge=100, le=32000, description="Maximum token budget for context"
    )


class CitationSource(BaseModel):
    document_id: uuid.UUID
    document_title: str | None
    filename: str
    chunk_index: int
    page_number: int | None
    section_heading: str | None
    heading_hierarchy: list[str]
    chunk_type: str


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    content: str
    source: CitationSource
    dense_rank: int | None = None
    sparse_rank: int | None = None
    rrf_score: float
    rerank_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    total_candidates: int
    returned_count: int
    results: list[RetrievedChunk]
