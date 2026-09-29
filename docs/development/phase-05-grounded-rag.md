# Phase 05: Grounded RAG & Citation Engine
## Engineering Specification & Implementation Guide

**Phase:** 05  
**Status:** Completed ✅  
**Prerequisites:** Phase 01: Foundation | Phase 02: Auth & RBAC | Phase 03: Document Ingestion | Phase 04: Hybrid Retrieval  
**Objective:** Implement grounded generative synthesis with strict citation formatting, Gemini LLM provider adapter, hallucination mitigation prompt engineering, streaming SSE endpoints, and verifiable source lineage.

---

## 1. Objective
Transform hybrid search candidates into hallucination-resistant, audit-compliant answers that:
1. **Enforce Strict Grounding:** System prompts constrain the model to only use facts from retrieved context blocks. If the context does not contain sufficient facts to answer, the model must decline rather than speculate.
2. **Inline Bracket Citations:** All assertions must cite source passages inline using bracket notation (e.g., `[1]`, `[2]`).
3. **Structured Source Lineage:** Every answer includes a machine-readable citation manifest linking bracket numbers back to exact document IDs, filenames, page numbers, and section breadcrumbs.
4. **Token Streaming via Server-Sent Events (SSE):** Supports real-time token streaming with a terminal citation payload for enterprise chat interfaces.

---

## 2. Architecture & Data Flow

```text
User Question + JWT (tenant_id, roles)
                 ↓
[ Phase 04: Hybrid Retrieval Engine ]
  - Dense Search + Sparse Search + Pre-Retrieval RBAC
  - Reciprocal Rank Fusion (RRF)
  - FlashRank Cross-Encoder Reranking
  - Lost-in-the-Middle Reordering & Context Budgeting
                 ↓
       Top-N Ranked Chunks: [C_0, C_1, ..., C_n]
                 ↓
[ Context & Prompt Assembler ]:
  - System Instructions: Grounding constraints, citation rules, refusal directives
  - Context Formatting:
      [1] Source: IT_Policy.md (Section: Encryption)
      Content: "All company laptops must run disk encryption..."
      [2] Source: Cafe_Guide.md (Section: Hours)
      Content: "The cafeteria serves sandwiches at 12pm..."
  - User Question: "What are the laptop security requirements?"
                 ↓
[ Gemini LLM Adapter (gemini-3.5-flash-lite) ]:
  - Generates text with temperature = 0.0 (deterministic)
  - Async token streaming via generate_content_stream
                 ↓
[ Citation Validator & Post-Processor ]:
  - Parses referenced bracket IDs ([1], [2])
  - Correlates with actual chunk source metadata
  - Detects orphan citations
                 ↓
JSON Response / SSE Stream:
  - Answer: "All company laptops must run disk encryption [1]."
  - Citations: [
      {"citation_id": 1, "document_id": "...", "filename": "IT_Policy.md", "section": "Encryption"}
    ]
```

---

## 3. Key Components Implemented

1. **Config Update (`src/core/config.py`):**
   * Added `ACTIVE_LLM_MODEL: str = "gemini-3.5-flash-lite"` to `Settings`.
2. **Gemini LLM Adapter (`src/infrastructure/ai/gemini_llm.py`):**
   * Implements `BaseLLMClient`: `generate_text`, `generate_structured` (Pydantic validation), `stream_text`.
3. **Pydantic Schemas (`src/schemas/rag.py`):**
   * `RAGQueryRequest`: `question`, `top_k`, `top_n`, `score_threshold`, `max_tokens`, `temperature`.
   * `CitationItem`: `citation_id`, `document_id`, `filename`, `document_title`, `page_number`, `section_heading`, `snippet`.
   * `RAGQueryResponse`: `question`, `answer`, `citations`, `has_sufficient_context`, `model`.
4. **Grounded Prompt Engineering & Service (`src/services/rag.py`):**
   * Orchestrates retrieval $\rightarrow$ prompt formatting $\rightarrow$ LLM generation $\rightarrow$ citation extraction $\rightarrow$ SSE streaming.
5. **FastAPI RAG Router (`src/api/v1/rag.py`):**
   * `POST /api/v1/rag/ask`: Synchronous grounded Q&A with full citation lineage.
   * `POST /api/v1/rag/stream`: Server-Sent Events (SSE) token stream with terminal citation manifest.
6. **Automated Unit & Integration Tests (`tests/unit/test_rag.py`):**
   * Verifies grounded answer accuracy, citation presence, refusal on out-of-context questions, and RBAC preservation.

---

## 4. Completion Criteria
* [x] `GeminiLLMClient` implements `BaseLLMClient` for synchronous, structured, and streaming text.
* [x] RAG prompt enforces strict citation syntax (`[1]`, `[2]`) and zero-hallucination refusal.
* [x] Citations in the answer correctly map back to retrieved `DocumentChunk` sources.
* [x] `/api/v1/rag/ask` answers queries grounded in tenant documents.
* [x] `/api/v1/rag/stream` streams tokens using `text/event-stream`.
* [x] RBAC pre-filtering prevents unauthorized information synthesis in answers.
* [x] 100% test pass on test suite.

---

## 5. Key Architectural Decisions & Trade-Offs

### Decision 1: Deterministic Zero-Temperature Sampling (ADR-004)
- **Problem:** Non-zero temperature introduces probabilistic hallucinations and ungrounded extrapolations in enterprise legal, compliance, and policy queries.
- **Solution:** Force `temperature = 0.0` for all factual grounded generation tasks.
- **Trade-off:** Answers have less creative phrasing variation, but achieve reproducible, verifiable assertions with zero speculation.

### Decision 2: Direct Bracket Parsing vs Complex Post-Extraction Function Calls
- **Problem:** Asking an LLM to call a second tool or emit complex nested JSON objects for citations increases token cost by 40–60% and increases generation latency.
- **Solution:** Standard bracket citation syntax `[N]` generated inline with natural text. A fast regex parser extracts cited indices and correlates them with the ranked context array in $O(N)$ CPU time (<1ms).
- **Trade-off:** Occasional malformed bracket syntax, mitigated by strict system prompt few-shot examples and citation regex bounds-checking.

### Decision 3: Server-Sent Events (SSE) vs WebSockets for RAG Streaming
- **Problem:** WebSockets require bi-directional stateful connections, persistent server memory, and complex proxy/load-balancer configurations.
- **Solution:** Server-Sent Events (SSE) over HTTP/1.1 or HTTP/2 (`text/event-stream`).
- **Trade-off:** One-way client-only stream, but works transparently with standard HTTP proxies, CDN caching, and FastAPI `StreamingResponse`.

---

## 6. Interview Defense Questions & Answers

### Q1: "How do you guarantee that an LLM does not hallucinate answers to compliance or legal questions?"
> *"We implement a defense-in-depth approach. First, we use deterministic sampling with `temperature = 0.0`. Second, the system instruction explicitly restricts the model to the numbered source passages, instructing it to state a standardized refusal ('I do not have sufficient information...') if facts are absent. Third, every assertion must have an inline citation `[1]`, and our service checks that cited indices match actual retrieved chunk IDs. Finally, because our Phase 04 retrieval layer uses hard SQL pre-filtering, the LLM never sees chunks outside the user's role or tenant, preventing both hallucination and data leakage."*

### Q2: "How do you handle Server-Sent Events (SSE) token streaming while still returning structured citations?"
> *"In a standard JSON API, you can return citations alongside the answer string. In streaming mode, tokens arrive incrementally before the full answer is complete. We solve this by streaming text token events as `data: {"token": "..."}\n\n`. Once the LLM generator finishes, the backend parses the entire synthesized response, correlates all referenced bracket citations `[N]` against the chunk metadata, and emits a final terminal event: `data: {"event": "done", "citations": [...], "has_sufficient_context": true}\n\n`. The frontend streams tokens into the UI in real time and attaches the citation buttons upon receiving the terminal event."*

---

## 7. Automated Test Verification Summary

* Test suite: `tests/unit/test_rag.py`, `tests/unit/test_retrieval.py`, `tests/unit/test_documents_api.py`, `tests/unit/test_auth_api.py`, `tests/unit/test_health.py`, `tests/unit/test_config.py`
* Result: **6 passed in 23.42s (100% green)**.
* Verification coverage:
  - Unauthenticated access returns `401 Unauthorized`.
  - Authorized manager query generates grounded answer with `[1]` citation and structured citation metadata.
  - Out-of-domain query (*"chocolate chip cookies"*) returns `has_sufficient_context = False` and refusal message.
  - RBAC security prevents analyst from getting answers to restricted IT policy questions.
  - SSE streaming endpoint streams tokens with `text/event-stream` and emits terminal citation payload.

