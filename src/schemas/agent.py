import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from src.schemas.rag import CitationItem
from src.schemas.sql import SQLQueryResult


class ExecutionRoute(StrEnum):
    """Execution pathway determined by the Query Dispatcher."""

    RAG = "RAG"  # Direct unstructured document retrieval
    SQL = "SQL"  # Direct structured operational data query
    HYBRID_AGENT = "HYBRID_AGENT"  # Multi-step LangGraph stateful orchestration


class AgentQueryRequest(BaseModel):
    """User query request for the unified dispatcher & orchestrator."""

    prompt: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural language query, comparative question, or analytical prompt.",
    )
    force_route: ExecutionRoute | None = Field(
        default=None,
        description="Optional manual override to force a specific execution path.",
    )


class PlanStep(BaseModel):
    """Individual reasoning step executed in the LangGraph agent state machine."""

    step_number: int
    action: str
    target: str
    status: str
    output_summary: str | None = None


class AgentQueryResponse(BaseModel):
    """Unified response representing synthesized hybrid intelligence or routed result."""

    prompt: str
    route_selected: ExecutionRoute
    answer: str
    plan_steps: list[PlanStep] = Field(default_factory=list)
    citations: list[CitationItem] = Field(default_factory=list)
    sql_results: list[SQLQueryResult] = Field(default_factory=list)
    execution_time_ms: float
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
