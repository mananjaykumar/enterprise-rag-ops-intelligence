import asyncio
import json
import logging
import time
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User
from src.domain.interfaces.llm import BaseLLMClient
from src.infrastructure.ai.gemini_llm import GeminiLLMClient
from src.schemas.agent import (
    AgentQueryRequest,
    AgentQueryResponse,
    ExecutionRoute,
    PlanStep,
)
from src.schemas.rag import CitationItem, RAGQueryRequest
from src.schemas.sql import NaturalLanguageSQLRequest, SQLQueryResult
from src.services.rag import RAGService
from src.services.router import QueryRouterService
from src.services.text_to_sql import TextToSQLService

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    user_query: str
    tenant_id: str
    user_roles: list[str]
    user_id: str
    route: str
    route_reasoning: str
    plan_steps: list[dict[str, Any]]
    rag_subquery: str | None
    rag_answer: str | None
    rag_citations: list[dict[str, Any]]
    sql_subquery: str | None
    sql_result: dict[str, Any] | None
    final_response: str
    error: str | None


PLANNER_SYSTEM_INSTRUCTION = """You are a senior query planner for an enterprise intelligence system.
The user wants to analyze or cross-reference unstructured document information with structured operational data.

Break down the user query into:
1. 'document_question': A focused question to search company documentation, policies, standard operating procedures, or contracts.
2. 'database_question': A focused natural language question to query relational database tables (departments, employees, vendors, contracts, invoices, operational expenses).

STRICT JSON FORMAT:
Return ONLY a valid JSON object with no markdown:
{
  "document_question": "...",
  "database_question": "..."
}
"""

SYNTHESIZER_SYSTEM_INSTRUCTION = """You are a senior enterprise intelligence analyst.
Your task is to synthesize findings from company documentation and operational database queries to answer the user request.

INSTRUCTIONS:
1. Provide a clear, executive-level answer that directly resolves the user query.
2. Clearly compare the document rules or limits with the actual database figures.
3. Explicitly highlight any non-compliant claims, budget overruns, or policy discrepancies.
4. Write in clean, simple, standard English that anyone can easily understand. Avoid technical jargon or foreign phrases.
"""


class AgentOrchestrator:
    """Stateful multi-step agent orchestrator coordinating RAG and Text-to-SQL via LangGraph.

    Performance design:
    - RAG-only and SQL-only queries flow through dedicated single nodes (~12s / ~8s).
    - HYBRID_AGENT queries run RAG and SQL **concurrently** via a parallel node
      (asyncio.gather), then merge results before synthesis. This cuts HYBRID
      latency from ~34s (serial) to ~20s (parallel wall-clock time).
    """

    def __init__(
        self,
        rag_service: RAGService | None = None,
        text_to_sql_service: TextToSQLService | None = None,
        router_service: QueryRouterService | None = None,
        llm_client: BaseLLMClient | None = None,
    ) -> None:
        self.rag_service = rag_service or RAGService()
        self.text_to_sql_service = text_to_sql_service or TextToSQLService()
        self.router_service = router_service or QueryRouterService()
        self.llm_client = llm_client or GeminiLLMClient()
        self.graph = self._build_graph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self):
        """Constructs and compiles the LangGraph StateGraph.

        Graph topology:
            START → planner ─┬─ (RAG)          → rag_step      → synthesizer → END
                             ├─ (SQL)          → sql_step      → synthesizer → END
                             └─ (HYBRID_AGENT) → parallel_step → synthesizer → END
        """
        workflow = StateGraph(AgentState)

        workflow.add_node("planner", self._planner_node)
        workflow.add_node("rag_step", self._rag_node)
        workflow.add_node("sql_step", self._sql_node)
        workflow.add_node("parallel_step", self._parallel_rag_sql_node)  # NEW: concurrent RAG+SQL
        workflow.add_node("synthesizer", self._synthesizer_node)

        workflow.add_edge(START, "planner")

        # Route planner output to the appropriate execution node
        def _route_after_planner(state: AgentState) -> str:
            route = state["route"]
            if route == "HYBRID_AGENT":
                return "parallel_step"
            if route == "RAG":
                return "rag_step"
            return "sql_step"

        workflow.add_conditional_edges(
            "planner",
            _route_after_planner,
            {
                "rag_step": "rag_step",
                "sql_step": "sql_step",
                "parallel_step": "parallel_step",
            },
        )

        # All three execution paths converge at synthesizer
        workflow.add_edge("rag_step", "synthesizer")
        workflow.add_edge("sql_step", "synthesizer")
        workflow.add_edge("parallel_step", "synthesizer")
        workflow.add_edge("synthesizer", END)

        return workflow.compile()

    # ------------------------------------------------------------------
    # Planner node
    # ------------------------------------------------------------------

    async def _planner_node(self, state: AgentState) -> dict[str, Any]:
        """Plans the sub-queries and execution steps based on the identified route."""
        route = state["route"]
        query = state["user_query"]
        plan_steps: list[dict[str, Any]] = []

        if route == "RAG":
            plan_steps.append(
                {
                    "step_number": 1,
                    "action": "RETRIEVE_DOCUMENTS",
                    "target": "Unstructured Knowledge Base",
                    "status": "PENDING",
                    "output_summary": None,
                }
            )
            return {"rag_subquery": query, "plan_steps": plan_steps}

        if route == "SQL":
            plan_steps.append(
                {
                    "step_number": 1,
                    "action": "QUERY_DATABASE",
                    "target": "Operational Database",
                    "status": "PENDING",
                    "output_summary": None,
                }
            )
            return {"sql_subquery": query, "plan_steps": plan_steps}

        # HYBRID_AGENT: decompose into focused sub-questions for each source
        plan_prompt = f"USER QUERY: {query}\n\nPLAN JSON:"
        rag_subquery = query
        sql_subquery = query

        try:
            raw_plan = await self.llm_client.generate_text(
                prompt=plan_prompt,
                system_instruction=PLANNER_SYSTEM_INSTRUCTION,
                temperature=0.0,
            )
            clean_plan = raw_plan.strip()
            if clean_plan.startswith("```"):
                lines = clean_plan.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                clean_plan = "\n".join(lines).strip()

            parsed = json.loads(clean_plan)
            rag_subquery = parsed.get("document_question", query)
            sql_subquery = parsed.get("database_question", query)
        except Exception as exc:
            logger.warning("Hybrid sub-query decomposition failed: %s; using original query", exc)

        plan_steps.extend(
            [
                {
                    "step_number": 1,
                    "action": "RETRIEVE_DOCUMENTS",
                    "target": "Policy Documentation & Standard Operating Procedures",
                    "status": "PENDING",
                    "output_summary": None,
                },
                {
                    "step_number": 2,
                    "action": "QUERY_DATABASE",
                    "target": "Operational Expenses, Invoices, and Budgets",
                    "status": "PENDING",
                    "output_summary": None,
                },
                {
                    "step_number": 3,
                    "action": "SYNTHESIZE_REPORT",
                    "target": "Executive Intelligence Briefing",
                    "status": "PENDING",
                    "output_summary": None,
                },
            ]
        )

        return {
            "rag_subquery": rag_subquery,
            "sql_subquery": sql_subquery,
            "plan_steps": plan_steps,
        }

    # ------------------------------------------------------------------
    # Individual execution nodes (used by RAG-only and SQL-only routes)
    # ------------------------------------------------------------------

    async def _rag_node(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        """Executes grounded document retrieval."""
        configurable = config.get("configurable", {})
        db: AsyncSession = configurable["db"]
        user: User = configurable["user"]
        subquery = state.get("rag_subquery") or state["user_query"]

        plan_steps = list(state["plan_steps"])
        for step in plan_steps:
            if step["action"] == "RETRIEVE_DOCUMENTS":
                step["status"] = "IN_PROGRESS"

        try:
            rag_res = await self.rag_service.answer(
                db=db,
                user=user,
                request=RAGQueryRequest(question=subquery),
            )
            citations_data = [c.model_dump() for c in rag_res.citations]
            for step in plan_steps:
                if step["action"] == "RETRIEVE_DOCUMENTS":
                    step["status"] = "COMPLETED"
                    step["output_summary"] = f"Retrieved {len(rag_res.citations)} citations."

            return {
                "rag_answer": rag_res.answer,
                "rag_citations": citations_data,
                "plan_steps": plan_steps,
            }
        except Exception as exc:
            logger.error("RAG node execution failed: %s", exc)
            for step in plan_steps:
                if step["action"] == "RETRIEVE_DOCUMENTS":
                    step["status"] = "FAILED"
                    step["output_summary"] = str(exc)
            return {
                "rag_answer": f"Document retrieval failed: {exc}",
                "rag_citations": [],
                "plan_steps": plan_steps,
                "error": str(exc),
            }

    async def _sql_node(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        """Executes operational SQL query within the 5-gate sandbox."""
        configurable = config.get("configurable", {})
        db: AsyncSession = configurable["db"]
        user: User = configurable["user"]
        subquery = state.get("sql_subquery") or state["user_query"]

        plan_steps = list(state["plan_steps"])
        for step in plan_steps:
            if step["action"] == "QUERY_DATABASE":
                step["status"] = "IN_PROGRESS"

        try:
            sql_req = NaturalLanguageSQLRequest(prompt=subquery, explain=True)
            sql_res = await self.text_to_sql_service.execute_query(
                db=db,
                user=user,
                request=sql_req,
            )
            sql_dict = sql_res.model_dump()
            for step in plan_steps:
                if step["action"] == "QUERY_DATABASE":
                    step["status"] = "COMPLETED"
                    step["output_summary"] = (
                        f"Returned {sql_res.row_count} rows in {sql_res.execution_time_ms}ms."
                    )

            return {
                "sql_result": sql_dict,
                "plan_steps": plan_steps,
            }
        except Exception as exc:
            logger.error("SQL node execution failed: %s", exc)
            for step in plan_steps:
                if step["action"] == "QUERY_DATABASE":
                    step["status"] = "FAILED"
                    step["output_summary"] = str(exc)
            return {
                "sql_result": None,
                "plan_steps": plan_steps,
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Parallel execution node (HYBRID_AGENT only)
    # ------------------------------------------------------------------

    async def _parallel_rag_sql_node(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Runs RAG and SQL concurrently using asyncio.gather, then merges results.

        Both sub-tasks are fully independent — they use separate Gemini calls,
        separate DB queries, and write to different state keys — so there is no
        data race. If either fails, the error is captured and the pipeline
        continues gracefully so the synthesizer still produces a partial answer.
        """
        logger.info("HYBRID_AGENT: launching RAG and SQL in parallel")
        t_start = time.perf_counter()

        rag_task = self._rag_node(state, config)
        sql_task = self._sql_node(state, config)

        rag_result, sql_result = await asyncio.gather(
            rag_task,
            sql_task,
            return_exceptions=True,  # don't let one failure kill the other
        )

        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
        logger.info("Parallel RAG+SQL completed in %.0f ms", elapsed_ms)

        # --- Handle exceptions from either branch gracefully ---
        if isinstance(rag_result, BaseException):
            logger.error("Parallel RAG branch raised an exception: %s", rag_result)
            rag_result = {
                "rag_answer": f"Document retrieval failed: {rag_result}",
                "rag_citations": [],
                "plan_steps": state["plan_steps"],
                "error": str(rag_result),
            }

        if isinstance(sql_result, BaseException):
            logger.error("Parallel SQL branch raised an exception: %s", sql_result)
            sql_result = {
                "sql_result": None,
                "plan_steps": state["plan_steps"],
                "error": str(sql_result),
            }

        # --- Merge plan_steps from both branches ---
        # Each branch returned its own copy of plan_steps with updated statuses.
        # We merge them by action name so each step reflects the correct outcome.
        rag_steps_by_action = {s["action"]: s for s in rag_result.get("plan_steps", [])}
        sql_steps_by_action = {s["action"]: s for s in sql_result.get("plan_steps", [])}

        merged_steps = list(state["plan_steps"])  # start from original order
        for step in merged_steps:
            action = step["action"]
            if action in rag_steps_by_action:
                step.update(rag_steps_by_action[action])
            elif action in sql_steps_by_action:
                step.update(sql_steps_by_action[action])

        # Collect errors from either branch (if any)
        errors = [
            v for v in [rag_result.get("error"), sql_result.get("error")] if v
        ]

        return {
            "rag_answer": rag_result.get("rag_answer"),
            "rag_citations": rag_result.get("rag_citations", []),
            "sql_result": sql_result.get("sql_result"),
            "plan_steps": merged_steps,
            **({"error": " | ".join(errors)} if errors else {}),
        }

    # ------------------------------------------------------------------
    # Synthesizer node
    # ------------------------------------------------------------------

    async def _synthesizer_node(self, state: AgentState) -> dict[str, Any]:
        """Synthesizes final intelligence response from RAG and/or SQL outputs."""
        route = state["route"]
        plan_steps = list(state["plan_steps"])

        if route == "RAG":
            return {"final_response": state.get("rag_answer") or "No document information found."}

        if route == "SQL":
            sql_data = state.get("sql_result")
            if sql_data:
                response = (
                    sql_data.get("explanation")
                    or f"Query returned {sql_data.get('row_count', 0)} rows."
                )
            else:
                response = "SQL query returned no results or failed."
            return {"final_response": response}

        # HYBRID_AGENT: synthesize both document rules and operational metrics
        for step in plan_steps:
            if step["action"] == "SYNTHESIZE_REPORT":
                step["status"] = "IN_PROGRESS"

        prompt = (
            f"USER QUERY:\n{state['user_query']}\n\n"
            f"DOCUMENT KNOWLEDGE & POLICY FINDINGS:\n{state.get('rag_answer', 'None')}\n\n"
            f"OPERATIONAL DATABASE RESULTS:\n{state.get('sql_result', {}).get('rows', [])}\n\n"
            f"EXECUTIVE SYNTHESIS:"
        )

        try:
            synthesized = await self.llm_client.generate_text(
                prompt=prompt,
                system_instruction=SYNTHESIZER_SYSTEM_INSTRUCTION,
                temperature=0.0,
            )
            for step in plan_steps:
                if step["action"] == "SYNTHESIZE_REPORT":
                    step["status"] = "COMPLETED"
                    step["output_summary"] = "Report synthesized successfully."

            return {
                "final_response": synthesized.strip(),
                "plan_steps": plan_steps,
            }
        except Exception as exc:
            logger.error("Synthesizer failed: %s", exc)
            for step in plan_steps:
                if step["action"] == "SYNTHESIZE_REPORT":
                    step["status"] = "FAILED"
                    step["output_summary"] = str(exc)

            fallback = (
                f"Findings Summary:\n\n"
                f"Policy Information:\n{state.get('rag_answer')}\n\n"
                f"Database Findings:\n{state.get('sql_result', {}).get('explanation')}"
            )
            return {
                "final_response": fallback,
                "plan_steps": plan_steps,
            }

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute_agent(
        self,
        db: AsyncSession,
        user: User,
        request: AgentQueryRequest,
    ) -> AgentQueryResponse:
        """Executes query through the unified dispatcher and LangGraph state machine."""
        start_time = time.perf_counter()

        # 1. Extract scalar user properties to avoid greenlet/session expiration issues
        user_tenant_id = str(user.tenant_id)
        user_id_str = str(user.id)
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        # 2. Classify route (document catalog awareness + fast heuristic, LLM fallback for ambiguous)
        route, reasoning = await self.router_service.route_query(
            prompt=request.prompt,
            force_route=request.force_route,
            db=db,
            tenant_id=user_tenant_id,
        )

        initial_state: AgentState = {
            "user_query": request.prompt,
            "tenant_id": user_tenant_id,
            "user_roles": [role_str],
            "user_id": user_id_str,
            "route": route.value,
            "route_reasoning": reasoning,
            "plan_steps": [],
            "rag_subquery": None,
            "rag_answer": None,
            "rag_citations": [],
            "sql_subquery": None,
            "sql_result": None,
            "final_response": "",
            "error": None,
        }

        # 3. Execute LangGraph workflow
        config: RunnableConfig = {"configurable": {"db": db, "user": user}}
        final_state = await self.graph.ainvoke(initial_state, config=config)

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        citations = [CitationItem(**c) for c in final_state.get("rag_citations", [])]
        sql_results = []
        if final_state.get("sql_result"):
            sql_results.append(SQLQueryResult(**final_state["sql_result"]))

        plan_steps = [PlanStep(**s) for s in final_state.get("plan_steps", [])]

        return AgentQueryResponse(
            prompt=request.prompt,
            route_selected=ExecutionRoute(final_state["route"]),
            answer=final_state.get("final_response", ""),
            plan_steps=plan_steps,
            citations=citations,
            sql_results=sql_results,
            execution_time_ms=execution_time_ms,
        )
