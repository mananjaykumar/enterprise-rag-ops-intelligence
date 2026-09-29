import pytest

from src.schemas.agent import ExecutionRoute
from src.schemas.evaluation import (
    GoldenSQLCase,
    RetrievalMetrics,
)
from src.services.evaluation import EvaluationService

# =========================================================================
# 1. RETRIEVAL METRICS (L1 DETERMINISTIC)
# =========================================================================


def test_retrieval_metrics_calculation():
    """Verifies mathematical correctness of Hit Rate@1, @3, @5 and MRR."""
    # 3 sample queries:
    # Query 1: Target found at rank 1 -> Hit@1, Hit@3, Hit@5, RR = 1.0
    # Query 2: Target found at rank 3 -> Miss@1, Hit@3, Hit@5, RR = 1/3 (0.3333)
    # Query 3: Target found at rank 6 -> Miss@1, Miss@3, Miss@5, RR = 0.0
    ranked_results = [
        ["Corporate Travel Policy", "Security SOP", "Office Manual"],
        ["Employee Code of Conduct", "Expense Guide", "Corporate Travel Policy"],
        ["Doc A", "Doc B", "Doc C", "Doc D", "Doc E", "Doc F"],
    ]
    expected_targets = [
        "Corporate Travel Policy",
        "Corporate Travel Policy",
        "Corporate Travel Policy",
    ]

    metrics = EvaluationService.calculate_retrieval_metrics(ranked_results, expected_targets)

    assert metrics.total_queries == 3
    # 1 out of 3 had target at rank 1
    assert metrics.hit_rate_at_1 == round(1 / 3, 4)
    # 2 out of 3 had target in top 3
    assert metrics.hit_rate_at_3 == round(2 / 3, 4)
    # 2 out of 3 had target in top 5
    assert metrics.hit_rate_at_5 == round(2 / 3, 4)
    # MRR: (1.0 + 1/3 + 0) / 3 = 1.3333 / 3 = 0.4444
    assert metrics.mrr == round((1.0 + 1 / 3 + 0.0) / 3, 4)


def test_retrieval_metrics_empty():
    """Handles empty queries gracefully."""
    metrics = EvaluationService.calculate_retrieval_metrics([], [])
    assert metrics.total_queries == 0
    assert metrics.hit_rate_at_1 == 0.0
    assert metrics.mrr == 0.0


# =========================================================================
# 2. TEXT-TO-SQL AST & WHITELIST VALIDATION
# =========================================================================


def test_sql_validation_valid_and_expected():
    """Verifies that a compliant SELECT query matching expected tables passes."""
    case = GoldenSQLCase(
        query_id="SQL-001",
        prompt="Get Engineering department annual budget",
        expected_tables=["departments"],
        expected_columns=["annual_budget"],
        expected_sql_fragment="FROM departments",
    )
    sql = "SELECT name, annual_budget FROM departments WHERE code = 'ENG';"
    score = EvaluationService.validate_sql_query(sql, case)

    assert score.ast_valid is True
    assert score.tables_whitelisted is True
    assert score.execution_success is True
    assert score.matched_expected_tables is True
    assert score.error_message is None


def test_sql_validation_rejects_non_select():
    """Rejects DELETE/DROP queries during AST evaluation."""
    case = GoldenSQLCase(
        query_id="SQL-002",
        prompt="Delete Engineering department",
        expected_tables=["departments"],
        expected_sql_fragment="DELETE",
    )
    sql = "DELETE FROM departments WHERE code = 'ENG';"
    score = EvaluationService.validate_sql_query(sql, case)

    assert score.ast_valid is False
    assert score.execution_success is False
    assert "not a SELECT" in (score.error_message or "")


def test_sql_validation_detects_unauthorized_table():
    """Flags queries accessing unwhitelisted tables like 'users'."""
    case = GoldenSQLCase(
        query_id="SQL-003",
        prompt="Get all passwords",
        expected_tables=["users"],
        expected_sql_fragment="users",
    )
    sql = "SELECT email, hashed_password FROM users;"
    score = EvaluationService.validate_sql_query(sql, case)

    assert score.ast_valid is True
    assert score.tables_whitelisted is False
    assert "Unauthorized tables referenced" in (score.error_message or "")


# =========================================================================
# 3. ROUTE ACCURACY & QUALITY GATE
# =========================================================================


def test_routing_accuracy():
    """Verifies routing accuracy computation."""
    actual = [
        ExecutionRoute.RAG,
        ExecutionRoute.SQL,
        ExecutionRoute.RAG,
        ExecutionRoute.HYBRID_AGENT,
    ]
    expected = [
        ExecutionRoute.RAG,
        ExecutionRoute.SQL,
        ExecutionRoute.HYBRID_AGENT,
        ExecutionRoute.HYBRID_AGENT,
    ]

    metric = EvaluationService.calculate_routing_accuracy(actual, expected)
    assert metric.total_queries == 4
    assert metric.correct_routes == 3
    assert metric.accuracy == 0.75


def test_quality_gate_pass_and_fail():
    """Verifies quality gate threshold enforcement."""
    passing_retrieval = RetrievalMetrics(
        total_queries=10,
        hit_rate_at_1=0.7,
        hit_rate_at_3=0.9,
        hit_rate_at_5=1.0,
        mrr=0.82,
    )

    # All passing
    report_pass = EvaluationService.evaluate_quality_gate(
        retrieval_metrics=passing_retrieval,
        avg_faithfulness=0.88,
        avg_relevance=0.92,
        sql_ast_pass_rate=1.0,
        routing_accuracy=0.90,
    )
    assert report_pass.quality_gate_passed is True

    # Failing due to low faithfulness (hallucination)
    report_fail = EvaluationService.evaluate_quality_gate(
        retrieval_metrics=passing_retrieval,
        avg_faithfulness=0.60,  # Below 0.75 threshold
        avg_relevance=0.92,
        sql_ast_pass_rate=1.0,
        routing_accuracy=0.90,
    )
    assert report_fail.quality_gate_passed is False


# =========================================================================
# 4. GROUNDEDNESS & FAITHFULNESS (L2 MODEL-AS-A-JUDGE)
# =========================================================================


@pytest.mark.asyncio
async def test_groundedness_llm_judge_faithful_and_hallucination():
    """Live LLM judge test verifying high score on faithful facts and low score on hallucinations."""
    service = EvaluationService()

    context = [
        (
            "Corporate Travel and Expense Policy 2025: Section 4.1.\n"
            "The standard daily spending allowance limit for employee hotel lodging is exactly $200.00 per night. "
            "Any employee lodging expense claim exceeding $200.00 per day without prior executive approval is strictly non-compliant."
        )
    ]
    question = "What is the maximum allowed daily spending limit for employee hotel lodging?"

    # Case A: Faithful Response
    faithful_response = (
        "According to the Corporate Travel and Expense Policy (Section 4.1), the standard daily spending "
        "allowance limit for employee hotel lodging is exactly $200.00 per night. Any claims above this amount "
        "require prior executive approval."
    )
    score_faithful = await service.evaluate_groundedness(question, context, faithful_response)
    assert score_faithful.faithfulness_score >= 0.8
    assert score_faithful.answer_relevance_score >= 0.8
    assert len(score_faithful.unsupported_claims) == 0

    # Case B: Hallucinated Response (introducing ungrounded claims about free luxury upgrades & $500 limits)
    hallucinated_response = (
        "Employees can spend up to $500.00 per night at luxury resorts, and everyone receives free spa "
        "access and five-star complimentary breakfast vouchers."
    )
    score_hallucinated = await service.evaluate_groundedness(
        question, context, hallucinated_response
    )
    assert score_hallucinated.faithfulness_score < 0.6
    assert len(score_hallucinated.unsupported_claims) > 0
