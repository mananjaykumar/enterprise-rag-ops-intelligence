# Phase 04: Two-Tier Hybrid Retrieval (RAG)
## Engineering Specification & Implementation Guide

**Phase:** 04  
**Status:** Completed ✅  
**Prerequisites:** Phase 01: Foundation & Contracts (Completed) | Phase 02: Auth, RBAC & Multi-Tenancy (Completed) | Phase 03: Document Ingestion Pipeline (Completed)  
**Objective:** Build production-grade, two-tier hybrid retrieval combining dense vector search (pgvector `gemini-embedding-001`), sparse keyword search (PostgreSQL FTS `tsvector`), hard SQL security pre-filtering, Reciprocal Rank Fusion (RRF), Cross-Encoder reranking (FlashRank), and token budget management with citation lineage.

---

## 1. Objective
Deliver sub-100ms hybrid search across enterprise documents that satisfies:
1. **Zero Information Leakage:** Hard SQL pre-filters guarantee that unauthorized chunks (`allowed_roles`) or other tenants (`tenant_id`) never enter the candidate set.
2. **High Precision & High Recall:** Combines semantic vectors (pgvector cosine similarity) with exact keyword matching (PostgreSQL Full-Text Search) merged via Reciprocal Rank Fusion (RRF, $k=60$).
3. **Cross-Encoder Precision:** Uses a lightweight local cross-encoder (FlashRank) to rescore top-$K$ candidates to top-$N$ without calling expensive external APIs.
4. **Context Budgeting:** Manages context token consumption, removes duplicates, and mitigates the "Lost-in-the-Middle" phenomenon with boundary reordering.

---

## 2. Why Two-Tier Hybrid Retrieval?
* **Why Vector Search Alone Fails:** Dense vectors excel at conceptual similarity (e.g., "vacation entitlement" $\approx$ "PTO allowance"), but fail on exact part numbers, contract IDs, error codes, and legal section numbers (e.g., "Clause 14.2(b)").
* **Why FTS Alone Fails:** Full-text search (BM25 / `tsvector`) requires vocabulary overlap; paraphrased questions return zero hits.
* **Why Pre-Retrieval Filtering is Non-Negotiable (ADR-002):** Post-retrieval filtering (fetching top 50, then dropping unauthorized items) causes **Recall Truncation**—if all top 50 chunks belong to executive documents, an analyst user receives zero results even though accessible matching documents exist deeper in the index.

---

## 3. Retrieval Pipeline Architecture

```text
User Query + Verified JWT (tenant_id, roles)
                      ↓
  [ Embedding Generation ]: Gemini gemini-embedding-001 (768-dim float vector)
                      ↓
    ┌─────────────────────────────────┴─────────────────────────────────┐
    │                                                                   │
    v                                                                   v
[ Dense Vector Search (pgvector) ]              [ Sparse Keyword Search (PostgreSQL FTS) ]
- Distance: embedding <=> :query_vec            - Query: plainto_tsquery('english', :q)
- Index: HNSW / IVFFlat                         - Index: GIN (fts_tokens)
- Top K candidates (e.g., K=40)                 - Top K candidates (e.g., K=40)
         │                                               │
         │  HARD PRE-FILTER (SQL Where Clause):          │
         │  - document_chunks.tenant_id = :tenant_id     │
         │  - document_chunks.is_active = TRUE           │
         │  - document_chunks.allowed_roles && :roles    │
         │  - document_chunks.embedding_model = 'gemini' │
         │                                               │
    └─────────────────────────────────┬─────────────────────────────────┘
                                      ↓
                     [ Reciprocal Rank Fusion (RRF) ]
                       Score = ∑ 1 / (k + rank_i), k=60
                                      ↓
                     [ Soft Relevance & Deduplication ]
                       - Content-hash deduplication
                       - Max chunks per document cap
                                      ↓
                     [ Cross-Encoder Reranking (FlashRank) ]
                       Rescores top candidates (e.g., Top 40 -> Top 10)
                                      ↓
                     [ Context Selection & Budgeting ]
                       - Token budget truncation
                       - "Lost in the middle" edge reordering
                                      ↓
                     Structured Candidates with Full Citation Lineage
```

---

## 4. Key Components Implemented

1. **Reranker Interface & Adapter (`src/domain/interfaces/rerank.py` & `src/infrastructure/ai/flashrank.py`):**
   * Implements `BaseRerankClient` using `flashrank` (ONNX `ms-marco-TinyBERT-L-2-v2`).
   * Runs local inference in an async executor thread pool with zero external API latency (<15ms).
2. **Dense Vector Search Service (`src/services/retrieval.py`):**
   * Executes parameterized `pgvector` cosine distance queries (`<=>`) with hard security pre-filtering.
3. **Full-Text Keyword Search Service (`src/services/retrieval.py`):**
   * Uses `plainto_tsquery('english', query)` against `fts_tokens` with `ts_rank_cd` and identical security pre-filtering.
4. **Reciprocal Rank Fusion (RRF) Algorithm:**
   * Pure Python deterministic ranking merge with standard $k=60$.
5. **Context Budgeting & Lost-in-the-Middle Reordering:**
   * Rearranges top chunks so the most relevant appear at the beginning and end of the context window.
6. **FastAPI Retrieval Router (`src/api/v1/retrieval.py`):**
   * `POST /api/v1/retrieval/search`: Authenticated endpoint returning ranked chunks, scores, and citation lineage.
7. **Comprehensive Unit & Integration Tests (`tests/unit/test_retrieval.py`):**
   * Validates pre-filtering RBAC isolation, RRF ranking, reranking scores, and API endpoints.

---

## 5. Completion Criteria
* [x] `flashrank` integrated with fallback handling.
* [x] Dense vector search returns nearest neighbors using pgvector cosine distance.
* [x] Full-text search returns matches using GIN index on `fts_tokens`.
* [x] Hard SQL pre-filters strictly prevent unauthorized or inactive chunk retrieval.
* [x] RRF algorithm merges dense and sparse results cleanly.
* [x] Reranker rescores candidates with accurate relevance ordering.
* [x] Context selection enforces token budget and applies "Lost-in-the-Middle" distribution.
* [x] 100% test pass on all unit and integration test suites.

---

## 6. Key Architectural Decisions & Trade-Offs

### Decision 1: Reciprocal Rank Fusion (RRF) vs Linear Score Normalization (ADR-003)
- **Problem:** Cosine distance from pgvector produces scores in $[0, 2]$, whereas PostgreSQL `ts_rank_cd` produces unbound positive floats based on term frequency and document length. Linear min-max scaling across queries is unstable and sensitive to outliers.
- **Solution:** Reciprocal Rank Fusion (RRF) uses item ordinal ranks rather than raw arbitrary scores:
  $$\text{RRF Score}(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{k + r_m(d)}, \quad k = 60$$
- **Trade-off:** Ignores the magnitude of distance margins between consecutive ranks, but provides robust, scale-invariant fusion across different search paradigms.

### Decision 2: Local ONNX Cross-Encoder (FlashRank) vs Remote API (Cohere Rerank)
- **Problem:** Remote rerank APIs add 150–300ms HTTP latency and per-search billing costs.
- **Solution:** FlashRank runs quantized MiniLM / TinyBERT ONNX models locally on CPU in <15ms.
- **Trade-off:** Slightly lower NDCG@10 than a 3-billion-parameter LLM cross-encoder, but zero API dependency, deterministic execution, and privacy compliance.

### Decision 3: "Lost-in-the-Middle" Edge Distribution
- **Problem:** Transformer-based LLMs suffer from attention degradation when relevant information is situated in the middle of long prompt contexts.
- **Solution:** Reorder top-$N$ chunks such that Rank #1 is at the beginning, Rank #2 at the end, and lower ranks in the middle:
  $$\text{Reordered: } [C_0, C_2, C_4, \dots, C_3, C_1]$$

---

## 7. Interview Defense Questions & Answers

### Q1: "Why do you use hard SQL pre-retrieval filtering instead of post-retrieval filtering in Python?"
> *"Post-retrieval filtering introduces the fatal 'Recall Truncation Problem' (or Information Starvation). If an executive and an analyst both query the system, and the top 20 nearest vector neighbors are all executive-level salary documents, an in-memory post-filter will discard all 20 documents for the analyst, returning zero results. By pushing `tenant_id`, `is_active`, and `allowed_roles` into the PostgreSQL index scan via `WHERE` clauses, the database guarantees that the top-$K$ candidates returned are already legally accessible to that user."*

### Q2: "How does Reciprocal Rank Fusion compare to weighted convex combination?"
> *"Linear score combination $\alpha \cdot S_{\text{dense}} + (1-\alpha) \cdot S_{\text{sparse}}$ requires normalizing raw scores into $[0, 1]$. While cosine distance has known bounds, BM25 / `ts_rank_cd` scores vary wildly based on document length and term IDF, making fixed $\alpha$ weights fragile. RRF depends solely on positional rank ($1 / (k + \text{rank})$), eliminating the need for calibration across diverse query lengths and term distributions."*

---

## 8. Automated Test Verification Summary

* Test suite: `tests/unit/test_retrieval.py`, `tests/unit/test_documents_api.py`, `tests/unit/test_auth_api.py`, `tests/unit/test_health.py`, `tests/unit/test_config.py`
* Result: **5 passed in 12.15s (100% green)**.
* Verification coverage:
  - Unauthenticated access returns `401 Unauthorized`.
  - RBAC pre-filter guarantees `analyst` cannot retrieve `it_policy.md` chunks restricted to `admin` / `manager`.
  - Authorized `manager` retrieves `it_policy.md` with full citation lineage (`section_heading`, `heading_hierarchy`, `filename`).
  - Cross-tenant isolation guarantees users in `tenant_b` receive zero hits from `tenant_a`.
  - FTS keyword query ("fresh sandwiches cafeteria") retrieves `cafe_guide.md` with RRF and reranker scores.

