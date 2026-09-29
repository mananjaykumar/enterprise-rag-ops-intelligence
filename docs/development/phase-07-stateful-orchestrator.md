# Phase 07: Stateful Agent Orchestrator (LangGraph)
## Engineering Specification & Implementation Guide

**Phase:** 07  
**Status:** Completed ✅  
**Prerequisites:** Phase 01: Foundation | Phase 02: Auth & RBAC | Phase 03: Document Ingestion | Phase 04: Hybrid Retrieval | Phase 05: Grounded RAG | Phase 06: Secure Text-to-SQL  
**Objective:** Implement a unified Query Dispatcher and LangGraph-powered Stateful Agent Orchestrator coordinating deterministic single-intent routing (RAG vs. SQL) and multi-step hybrid reasoning loops across unstructured documents and operational databases.

---

## 1. Architectural Philosophy & Strategy

In enterprise production systems, deploying an autonomous ReAct loop for every user query is an architectural anti-pattern: it leads to unpredictable latency, high token consumption, and failure modes on simple lookups.

To balance speed, cost, and analytical depth, Phase 07 introduces a **Two-Tiered Hybrid Dispatcher**:
1. **Tier 1 (Deterministic Fast Path):** Single-intent queries are classified and dispatched directly to the deterministic Grounded RAG Pipeline or 5-Gate Text-to-SQL Sandbox with sub-second / low-latency execution.
2. **Tier 2 (Stateful LangGraph Agent):** Multi-intent, comparative, or analytical queries (e.g. *"Compare our travel policy daily spending allowance limits with actual Engineering expenses and identify non-compliant claims"*) are routed to a state machine graph that plans, queries both data stores, cross-references evidence, and synthesizes a comprehensive report.

```text
                                  User Natural Language Query
                                                │
                                                ▼
                             ┌──────────────────────────────────────┐
                             │   Tier 1: Intent Router / Classifier │
                             └──────────────────┬───────────────────┘
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 │ (Direct Unstructured)        │ (Direct Structured)          │ (Hybrid / Multi-Step)
                 ▼                              ▼                              ▼
      ┌────────────────────┐         ┌────────────────────┐         ┌────────────────────┐
      │   RAG Fast Path    │         │   SQL Fast Path    │         │ LangGraph Agentic  │
      │   (Phase 04 & 05)  │         │     (Phase 06)     │         │   State Machine    │
      └────────────────────┘         └────────────────────┘         └─────────┬──────────┘
                                                                              │
                                       ┌──────────────────────────────────────┴──────────────────┐
                                       │ State: plan_steps, rag_citations, sql_results, report   │
                                       ▼                                                         ▼
                             ┌───────────────────┐                                     ┌───────────────────┐
                             │   RAG Tool Node   │                                     │   SQL Tool Node   │
                             │ (Docs & Policies) │                                     │(Expenses/Invoices)│
                             └─────────┬─────────┘                                     └─────────┬─────────┘
                                       │                                                         │
                                       └──────────────────────┬──────────────────────────────────┘
                                                              ▼
                                                   ┌─────────────────────┐
                                                   │ Report Synthesizer  │
                                                   │  & Citation Merger  │
                                                   └─────────────────────┘
```

---

## 2. LangGraph State Machine Architecture

### 2.1 State Definition (`AgentState`)
```python
class AgentState(TypedDict):
    user_query: str
    tenant_id: str
    user_roles: list[str]
    user_id: str
    route: str  # "RAG" | "SQL" | "HYBRID_AGENT"
    route_reasoning: str
    plan_steps: list[dict[str, Any]]
    rag_subquery: str | None
    rag_answer: str | None
    rag_citations: list[dict[str, Any]]
    sql_subquery: str | None
    sql_result: dict[str, Any] | None
    final_response: str
    error: str | None
```

### 2.2 Graph Nodes & Transitions
1. **`planner`**:
   - For hybrid queries, breaks the complex goal into:
     - Document search target (e.g. "Find maximum daily lodging allowance limit in travel policy").
     - Structured query target (e.g. "Query actual employee lodging expenses by department").
2. **`rag_step`**:
   - Invokes `RAGService.answer()` with pre-retrieval tenant and role isolation.
   - Extracts structured facts and citations.
3. **`sql_step`**:
   - Invokes `TextToSQLService.execute_query()` with 5-gate AST sandbox enforcement.
   - Extracts tabular data and audit log records.
4. **`synthesizer`**:
   - Fuses unstructured policy constraints with structured operational metrics.
   - Calculates variances, detects compliance deviations, and compiles the final executive report.
   - Emits dual-source provenance: document chunk citations + verified SQL audit logs.

---

## 3. Implementation Summary

| Component | Module | Responsibility |
|---|---|---|
| Contracts | `src/schemas/agent.py` | `ExecutionRoute` enum (`RAG`, `SQL`, `HYBRID_AGENT`), `AgentQueryRequest`, `PlanStep`, `AgentQueryResponse`. |
| Router | `src/services/router.py` | Low-latency Gemini intent classifier determining optimal execution pathway. |
| Orchestrator | `src/services/agent_orchestrator.py` | Two-tiered dispatcher coordinating fast paths and the compiled LangGraph StateGraph. |
| API Layer | `src/api/v1/agent.py` | Authenticated `POST /api/v1/agent/query` endpoint with tenant context and role validation. |
| Test Suite | `tests/unit/test_agent.py` | Verifies intent classification accuracy, multi-step state execution, and tenant isolation. |

---

## 4. Architectural Decisions & Trade-Offs

### Decision 1: Two-Tiered Dispatch vs. Full Autonomous ReAct
- **Decision:** Use a deterministic intent classifier to bypass the agent graph entirely for single-intent queries.
- **Trade-off:** Minimal classification latency (~200ms) is introduced for all queries, but avoids the 5–10x latency and token cost of running multi-turn ReAct loops on simple lookups.

### Decision 2: LangGraph State Machine vs. AutoGen / CrewAI
- **Decision:** Standardized on LangGraph's compiled `StateGraph`.
- **Trade-off:** LangGraph provides deterministic state transitions, native AsyncIO support, cycle detection, and predictable checkpointing required in enterprise multi-tenant architectures, whereas conversational multi-agent frameworks introduce unbounded token loops.

### Decision 3: Eager User Scalar Extraction
- **Decision:** Extract scalar properties (`user_tenant_id`, `user_id_str`, `role_str`) before invoking the graph or database nodes.
- **Trade-off:** Prevents SQLAlchemy `MissingGreenlet` exceptions when transaction rollbacks expire model attributes during asynchronous graph steps.

---

## 5. Senior System Architect Interview Defense

### Q1: Why not allow the LLM to write Python code to merge the SQL and document results?
> **Defense:** Executing arbitrary Python code in an enterprise platform introduces severe Remote Code Execution (RCE) and security vulnerabilities. LangGraph restricts LLM actions to strictly typed declarative nodes (`RETRIEVE_DOCUMENTS`, `QUERY_DATABASE`, `SYNTHESIZE_REPORT`). Structured computation (such as expense filtering and threshold comparisons) is performed either in the PostgreSQL SQL engine or within isolated prompt synthesis with deterministic verification.

### Q2: How does the agent orchestrator guarantee multi-tenant security across multiple data sources?
> **Defense:** Multi-tenancy is not left to LLM prompt instructions. The orchestrator extracts the authenticated JWT `tenant_id` at the API boundary and injects it into both downstream executors:
> 1. In the RAG branch, `tenant_id` is applied as an exact SQL metadata filter on `document_chunks`.
> 2. In the Text-to-SQL branch, `tenant_id` is injected into the Abstract Syntax Tree (AST) using `sqlglot` on every table referenced in the query.

### Q3: What happens if one branch of the hybrid query fails (e.g. SQL timeout)?
> **Defense:** Each node wraps execution in structured try-except blocks. If `sql_step` fails or times out, the plan records `QUERY_DATABASE: FAILED` with the exact error. The graph transitions to `synthesizer`, which produces a partial findings summary acknowledging the successful document retrieval while reporting the database error, avoiding complete request failure.
