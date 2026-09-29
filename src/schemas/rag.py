import uuid

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000, description="User question or query")
    top_k: int = Field(default=20, ge=1, le=100, description="Candidate pool size for retrieval")
    top_n: int = Field(default=5, ge=1, le=20, description="Reranked chunks included in context")
    score_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum rerank score filter"
    )
    max_tokens: int = Field(
        default=4000, ge=100, le=32000, description="Maximum context token budget"
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="LLM temperature (0.0 for strict deterministic facts)",
    )


class CitationItem(BaseModel):
    citation_id: int
    document_id: uuid.UUID
    filename: str
    document_title: str | None
    page_number: int | None
    section_heading: str | None
    heading_hierarchy: list[str]
    snippet: str


class RAGQueryResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationItem]
    has_sufficient_context: bool
    model: str
