import logging

import sqlglot
from sqlglot import exp

from src.domain.interfaces.llm import BaseLLMClient
from src.infrastructure.ai.gemini_llm import GeminiLLMClient
from src.schemas.agent import ExecutionRoute
from src.schemas.evaluation import (
    EvaluationSummaryReport,
    GoldenSQLCase,
    GroundednessScore,
    RetrievalMetrics,
    RouteClassificationMetric,
    SQLValidationScore,
)

logger = logging.getLogger(__name__)

GROUNDEDNESS_JUDGE_PROMPT = """You are an impartial, rigorous evaluation judge assessing the quality of an enterprise AI response.
Evaluate the candidate response based strictly on the provided context passages and the user's question.

Context Passages:
{context_passages}

User Question:
{user_question}

Candidate Response:
{candidate_response}

Your task:
1. 'faithfulness_score': Float between 0.0 and 1.0 representing the proportion of statements in the Candidate Response that are directly substantiated by the Context Passages. If the response contains unsupported statements, fabrications, or external assumptions, deduct points accordingly.
2. 'answer_relevance_score': Float between 0.0 and 1.0 representing how directly and completely the response addresses the User Question.
3. 'unsupported_claims': A list of sentences or statements from the Candidate Response that lack factual support in the Context Passages.
4. 'reasoning': A brief explanation of your evaluation.

Return ONLY a valid JSON object matching this schema:
{{
  "faithfulness_score": float,
  "answer_relevance_score": float,
  "unsupported_claims": ["claim 1", "claim 2"],
  "reasoning": "brief explanation"
}}
"""


class EvaluationService:
    """Enterprise evaluation engine for Retrieval, Groundedness, SQL, and Routing quality."""

    def __init__(self, llm_client: BaseLLMClient | None = None) -> None:
        self.llm_client = llm_client or GeminiLLMClient()

    # =========================================================================
    # 1. RETRIEVAL METRICS (L1 DETERMINISTIC)
    # =========================================================================

    @staticmethod
    def calculate_retrieval_metrics(
        ranked_results_per_query: list[list[str]],
        expected_targets: list[str],
    ) -> RetrievalMetrics:
        """Calculates Hit Rate@1, @3, @5 and Mean Reciprocal Rank (MRR).

        Args:
            ranked_results_per_query: List of retrieved document titles/identifiers per query.
            expected_targets: Ground-truth target document title/identifier per query.
        """
        total_queries = len(expected_targets)
        if total_queries == 0:
            return RetrievalMetrics(
                total_queries=0,
                hit_rate_at_1=0.0,
                hit_rate_at_3=0.0,
                hit_rate_at_5=0.0,
                mrr=0.0,
            )

        hits_at_1 = 0
        hits_at_3 = 0
        hits_at_5 = 0
        reciprocal_ranks = []

        for retrieved_list, target in zip(ranked_results_per_query, expected_targets, strict=False):
            normalized_target = target.strip().lower()
            rank_found = 0

            for idx, candidate in enumerate(retrieved_list):
                if normalized_target in candidate.strip().lower():
                    rank_found = idx + 1
                    break

            if rank_found == 1:
                hits_at_1 += 1
            if 1 <= rank_found <= 3:
                hits_at_3 += 1
            if 1 <= rank_found <= 5:
                hits_at_5 += 1

            if rank_found > 0:
                reciprocal_ranks.append(1.0 / rank_found)
            else:
                reciprocal_ranks.append(0.0)

        return RetrievalMetrics(
            total_queries=total_queries,
            hit_rate_at_1=round(hits_at_1 / total_queries, 4),
            hit_rate_at_3=round(hits_at_3 / total_queries, 4),
            hit_rate_at_5=round(hits_at_5 / total_queries, 4),
            mrr=round(sum(reciprocal_ranks) / total_queries, 4),
        )

    # =========================================================================
    # 2. GENERATION GROUNDEDNESS & FAITHFULNESS (L2 MODEL-AS-A-JUDGE)
    # =========================================================================

    async def evaluate_groundedness(
        self,
        question: str,
        context_snippets: list[str],
        candidate_response: str,
    ) -> GroundednessScore:
        """Evaluates claim-level faithfulness and answer relevance using an LLM judge."""
        formatted_context = (
            "\n---\n".join(context_snippets) if context_snippets else "No context provided."
        )
        prompt = GROUNDEDNESS_JUDGE_PROMPT.format(
            context_passages=formatted_context,
            user_question=question,
            candidate_response=candidate_response,
        )

        try:
            return await self.llm_client.generate_structured(
                prompt=prompt,
                response_schema=GroundednessScore,
                system_instruction="You are an expert AI quality evaluation judge.",
                temperature=0.0,
            )

        except Exception as exc:
            logger.error("Groundedness evaluation failed: %s", exc)
            return GroundednessScore(
                faithfulness_score=0.0,
                answer_relevance_score=0.0,
                unsupported_claims=["Evaluation execution error occurred."],
                reasoning=f"LLM Judge execution failed: {exc}",
            )

    # =========================================================================
    # 3. TEXT-TO-SQL AST & INTEGRITY VALIDATION
    # =========================================================================

    @staticmethod
    def validate_sql_query(
        generated_sql: str,
        case: GoldenSQLCase,
        allowed_tables: set[str] | None = None,
    ) -> SQLValidationScore:
        """Validates generated SQL against AST grammar, whitelisted tables, and golden expectations."""
        whitelist = allowed_tables or {
            "departments",
            "employees",
            "vendors",
            "contracts",
            "invoices",
            "operational_expenses",
        }

        try:
            parsed = sqlglot.parse_one(generated_sql, read="postgres")
            if not isinstance(parsed, exp.Select):
                return SQLValidationScore(
                    ast_valid=False,
                    tables_whitelisted=False,
                    execution_success=False,
                    matched_expected_tables=False,
                    error_message="Query root is not a SELECT statement.",
                )

            # Check table whitelist
            tables_in_query = {t.name.lower() for t in parsed.find_all(exp.Table)}
            unauthorized = tables_in_query - whitelist
            if unauthorized:
                return SQLValidationScore(
                    ast_valid=True,
                    tables_whitelisted=False,
                    execution_success=False,
                    matched_expected_tables=False,
                    error_message=f"Unauthorized tables referenced: {unauthorized}",
                )

            # Check expected tables match
            expected_lower = {t.lower() for t in case.expected_tables}
            matched_expected = expected_lower.issubset(tables_in_query)

            return SQLValidationScore(
                ast_valid=True,
                tables_whitelisted=True,
                execution_success=True,
                matched_expected_tables=matched_expected,
                error_message=None
                if matched_expected
                else f"Missing expected tables: {expected_lower - tables_in_query}",
            )
        except Exception as exc:
            return SQLValidationScore(
                ast_valid=False,
                tables_whitelisted=False,
                execution_success=False,
                matched_expected_tables=False,
                error_message=f"SQL AST parse error: {exc}",
            )

    # =========================================================================
    # 4. ROUTE CLASSIFICATION METRIC
    # =========================================================================

    @staticmethod
    def calculate_routing_accuracy(
        actual_routes: list[ExecutionRoute],
        expected_routes: list[ExecutionRoute],
    ) -> RouteClassificationMetric:
        """Calculates percentage of queries classified into their expected execution route."""
        total = len(expected_routes)
        if total == 0:
            return RouteClassificationMetric(total_queries=0, correct_routes=0, accuracy=0.0)

        correct = sum(
            1 for act, exp in zip(actual_routes, expected_routes, strict=False) if act == exp
        )
        return RouteClassificationMetric(
            total_queries=total,
            correct_routes=correct,
            accuracy=round(correct / total, 4),
        )

    # =========================================================================
    # 5. AGGREGATE SUMMARY & QUALITY GATE
    # =========================================================================

    @staticmethod
    def evaluate_quality_gate(
        retrieval_metrics: RetrievalMetrics,
        avg_faithfulness: float,
        avg_relevance: float,
        sql_ast_pass_rate: float,
        routing_accuracy: float,
        min_hit_rate_at_3: float = 0.70,
        min_faithfulness: float = 0.75,
        min_sql_ast_pass_rate: float = 1.0,
        min_routing_accuracy: float = 0.80,
    ) -> EvaluationSummaryReport:
        """Checks metrics against enterprise production quality gate thresholds."""
        passed = (
            retrieval_metrics.hit_rate_at_3 >= min_hit_rate_at_3
            and avg_faithfulness >= min_faithfulness
            and sql_ast_pass_rate >= min_sql_ast_pass_rate
            and routing_accuracy >= min_routing_accuracy
        )

        return EvaluationSummaryReport(
            total_cases_evaluated=retrieval_metrics.total_queries,
            retrieval_metrics=retrieval_metrics,
            average_faithfulness=round(avg_faithfulness, 4),
            average_answer_relevance=round(avg_relevance, 4),
            sql_ast_pass_rate=round(sql_ast_pass_rate, 4),
            routing_accuracy=round(routing_accuracy, 4),
            quality_gate_passed=passed,
            details={
                "thresholds": {
                    "min_hit_rate_at_3": min_hit_rate_at_3,
                    "min_faithfulness": min_faithfulness,
                    "min_sql_ast_pass_rate": min_sql_ast_pass_rate,
                    "min_routing_accuracy": min_routing_accuracy,
                }
            },
        )
