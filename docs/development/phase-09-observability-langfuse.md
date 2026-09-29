# Phase 09: Observability & Langfuse
## Engineering Specification & Implementation Guide

**Phase:** 09  
**Status:** Completed ✅  
**Prerequisites:** Phase 01: Foundation | Phase 02: Auth & RBAC | Phase 03: Document Ingestion | Phase 04: Hybrid Retrieval | Phase 05: Grounded RAG | Phase 06: Secure Text-to-SQL | Phase 07: Stateful Agent Orchestrator | Phase 08: Evaluation & Test Harness  
**Objective:** Implement production observability with Langfuse and OpenTelemetry, establishing end-to-end distributed tracing across FastAPI requests, hybrid retrieval stages, Text-to-SQL sandboxes, and LangGraph agent execution with token tracking, latency instrumentation, and tenant-level cost attribution.

---

## 1. Architectural Philosophy & Strategy

In enterprise generative AI deployments, observability is not merely server monitoring—it is the operational backbone for security, cost control, latency debugging, and audit compliance.

Phase 09 introduces **Multi-Layered Observability**:
1. **Layer 1: HTTP Request & Span Tracing (OpenTelemetry / FastAPI Middleware)**
   - Injects a unique `X-Trace-ID` and measures duration with `X-Response-Time-Ms`.
   - Propagates tenant context (`tenant_id`, `user_id`) into all execution spans.
2. **Layer 2: AI Pipeline & LLM Tracing (Langfuse Client Adapter)**
   - Traces prompts, model generations, token consumption (prompt tokens, completion tokens), latency, and model hyperparameters across Gemini models.
   - Attaches tenant and user tags for multi-tenant billing and cost attribution.
3. **Layer 3: Agentic State Machine Observability**
   - Traces LangGraph state transitions (`planner`, `rag_step`, `sql_step`, `synthesizer`) as nested spans within the parent trace.
4. **Layer 4: Resilient / Graceful Fallback**
   - If Langfuse credentials are not configured or the Langfuse endpoint is unreachable, tracing degrades gracefully to local structured logging without failing user queries or adding latency.

```text
                               Client Request (JWT Bearer Token)
                                              │
                                              ▼
                         ┌──────────────────────────────────────────┐
                         │   FastAPI Observability Middleware       │
                         │   - Injects trace_id / correlation_id    │
                         │   - Injects X-Trace-ID & Latency Headers │
                         └────────────────────┬─────────────────────┘
                                              │
                                              ▼
                         ┌──────────────────────────────────────────┐
                         │   Langfuse Trace Context Manager         │
                         │   (Tenant, User, Tags, Session ID)       │
                         └────────────────────┬─────────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
         ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
         │ RAG Span            │   │ Text-to-SQL Span    │   │ LangGraph Agent     │
         │ - Hybrid Search     │   │ - Gemini SQL Gen    │   │ - Planner Span      │
         │ - FlashRank Rerank  │   │ - 5-Gate AST Check  │   │ - Tool Execution    │
         │ - Prompt & Citations│   │ - DB Query Latency  │   │ - Synthesis Span    │
         └──────────┬──────────┘   └──────────┬──────────┘   └──────────┬──────────┘
                    │                         │                         │
                    └─────────────────────────┼─────────────────────────┘
                                              ▼
                         ┌──────────────────────────────────────────┐
                         │   Langfuse Server (Cloud or Self-Hosted) │
                         │   - Live Traces & Latency Heatmaps       │
                         │   - Token & Cost Attribution by Tenant   │
                         │   - Error Distribution & Audit Metrics   │
                         └──────────────────────────────────────────┘
```

---

## 2. Implementation Summary

| Component | Module | Responsibility |
|---|---|---|
| Configuration | `src/core/config.py` | Added `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `LANGFUSE_ENABLED`. |
| Tracing Service | `src/services/observability.py` | Context managers for distributed trace spans, LLM generation tracking, and local `NullSpan` fallback. |
| HTTP Middleware | `src/api/middleware/observability.py` | Request timing, `X-Trace-ID` injection, incoming trace propagation, and structured access logs. |
| Lifespan Management | `src/main.py` | Clean startup and shutdown event flushing via `get_observability_service().flush()`. |
| Test Suite | `tests/unit/test_observability.py` | Verifies header attachment, incoming trace ID propagation, local fallback resilience, and singleton lifecycle. |

---

## 3. Architectural Decisions & Trade-Offs

### Decision 1: Context-Managed Local Fallback (NullTracer)
- **Decision:** Build a lightweight `NullSpan` fallback within `ObservabilityService` that activates when Langfuse keys are absent or disabled.
- **Trade-off:** Requires writing fallback context managers, but ensures the platform runs at maximum speed with zero network overhead in local development and automated CI/CD pipelines without requiring active cloud credentials.

### Decision 2: Correlation Header Propagation
- **Decision:** Inspect `request.headers.get("X-Trace-ID")` before generating a new UUID.
- **Trade-off:** If an upstream client, API gateway, or microservice provides an existing trace ID, preserving it guarantees end-to-end distributed trace continuity across microservice boundaries.

### Decision 3: Clean Flush on Lifespan Shutdown
- **Decision:** Execute `get_observability_service().flush()` inside FastAPI's async lifespan shutdown hook.
- **Trade-off:** Flushes asynchronous telemetry batches in memory before the process terminates, preventing loss of the final trace logs during autoscaling scale-down events.

---

## 4. Senior System Architect Interview Defense

### Q1: Why use Langfuse over standard APMs like Datadog or New Relic?
> **Defense:** Traditional APMs are built for HTTP endpoints and database calls; they lack native abstractions for LLM applications. Langfuse understands the generative AI lifecycle: prompt versioning, token-level usage breakdown (prompt tokens vs. completion tokens), model-specific cost calculation, and nested agent state transitions. It allows multi-tenant cost tracking per customer organization, which traditional APMs cannot easily correlate.

### Q2: How does the observability system protect against user data privacy violations (PII)?
> **Defense:** Enterprise security mandates that raw sensitive data does not leak into external observability platforms. In our architecture:
> 1. Authentication passwords and JWT tokens are stripped before traces are formed.
> 2. Document vector embeddings are represented as metadata dimensions (e.g. 768 float array length) rather than serializing raw vector coordinates into trace metadata.
> 3. If running in sensitive healthcare or finance environments, Langfuse can be self-hosted via Docker inside the same private VPC, preventing external cloud data egress.

### Q3: How do you prevent observability from degrading API latency?
> **Defense:** Tracing operations are completely asynchronous. Event queuing and batching occur in background memory buffers and are flushed over non-blocking HTTP transports without delaying the client's HTTP response. In local mode, the `NullSpan` context manager executes in under 0.05 milliseconds with zero network I/O.
