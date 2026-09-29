from typing import Any

from pydantic import BaseModel, Field

from src.schemas.agent import ExecutionRoute

# =========================================================================
# 1. GOLDEN BENCHMARK DATASET SCHEMAS
# =========================================================================


class GoldenRAGCase(BaseModel):
    """Ground-truth test case for Unstructured Document RAG."""

    query_id: str
    question: str
    expected_document_title: str
    expected_keywords: list[str] = Field(default_factory=list)
    ground_truth_answer: str


class GoldenSQLCase(BaseModel):
    """Ground-truth test case for Operational Text-to-SQL."""

    query_id: str
    prompt: str
    expected_tables: list[str]
    expected_columns: list[str] = Field(default_factory=list)
    expected_sql_fragment: str


class GoldenHybridCase(BaseModel):
    """Ground-truth test case for Multi-Step Cross-Domain Agent Reasoning."""

    query_id: str
    prompt: str
    expected_route: ExecutionRoute = ExecutionRoute.HYBRID_AGENT
    expected_policy_keyword: str
    expected_data_keyword: str


class GoldenBenchmarkDataset(BaseModel):
    """Container holding all benchmark cases for regression testing."""

    version: str = "1.0.0"
    rag_cases: list[GoldenRAGCase] = Field(default_factory=list)
    sql_cases: list[GoldenSQLCase] = Field(default_factory=list)
    hybrid_cases: list[GoldenHybridCase] = Field(default_factory=list)


# =========================================================================
# 2. EVALUATION METRIC SCHEMAS
# =========================================================================


class RetrievalMetrics(BaseModel):
    """Hit Rate@K and Mean Reciprocal Rank (MRR) scores."""

    total_queries: int
    hit_rate_at_1: float = Field(ge=0.0, le=1.0)
    hit_rate_at_3: float = Field(ge=0.0, le=1.0)
    hit_rate_at_5: float = Field(ge=0.0, le=1.0)
    mrr: float = Field(ge=0.0, le=1.0, description="Mean Reciprocal Rank")


class GroundednessScore(BaseModel):
    """LLM-as-a-judge score evaluating factual derivation from source context."""

    faithfulness_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Ratio of claims in the generated response directly supported by retrieved evidence",
    )
    answer_relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Degree to which the generated response directly answers the user's question",
    )
    unsupported_claims: list[str] = Field(default_factory=list)
    reasoning: str


class SQLValidationScore(BaseModel):
    """Validation results for a generated SQL statement."""

    ast_valid: bool
    tables_whitelisted: bool
    execution_success: bool
    matched_expected_tables: bool
    error_message: str | None = None


class RouteClassificationMetric(BaseModel):
    """Accuracy of Intent Classifier."""

    total_queries: int
    correct_routes: int
    accuracy: float = Field(ge=0.0, le=1.0)


class EvaluationSummaryReport(BaseModel):
    """Aggregate benchmark report across all dimensions."""

    total_cases_evaluated: int
    retrieval_metrics: RetrievalMetrics
    average_faithfulness: float
    average_answer_relevance: float
    sql_ast_pass_rate: float
    routing_accuracy: float
    quality_gate_passed: bool
    details: dict[str, Any] = Field(default_factory=dict)
