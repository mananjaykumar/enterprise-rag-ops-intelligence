# Enterprise Knowledge & Operations Intelligence Platform
## Comprehensive System Architecture & Technical Specification

**Document Version:** 1.0.0  
**Status:** `DATA ARCHITECTURE LOCKED` | `SYSTEM ARCHITECTURE SPECIFIED`  
**Target Roles:** Applied AI Engineer, GenAI Engineer, AI Backend Engineer, RAG/Retrieval Engineer, Agentic AI Engineer  
**Core Principle:** *Free to start, production-minded, cloud-portable, scalable when needed.*

---

## Table of Contents
1. [Product Overview & Business Domain](#1-product-overview--business-domain)
2. [User Personas & Core Use Cases](#2-user-personas--core-use-cases)
3. [System Architecture & Component Topology](#3-system-architecture--component-topology)
4. [Document Intelligence & Ingestion Pipeline](#4-document-intelligence--ingestion-pipeline)
5. [Two-Tier Hybrid Retrieval Architecture (RAG)](#5-two-tier-hybrid-retrieval-architecture-rag)
6. [Secure Text-to-SQL Architecture](#6-secure-text-to-sql-architecture)
7. [Unified Database Schemas & Data Model](#7-unified-database-schemas--data-model)
8. [Architecture Decision Records (ADRs)](#8-architecture-decision-records-adrs)
9. [End-to-End Data Flows](#9-end-to-end-data-flows)
10. [Observability, Evaluation & Reliability Strategy](#10-observability-evaluation--reliability-strategy)
11. [Cloud Portability & Free-First Deployment Strategy](#11-cloud-portability--free-first-deployment-strategy)
12. [Phased Implementation Roadmap](#12-phased-implementation-roadmap)
13. [Interview Defense & Engineering Knowledge Guide](#13-interview-defense--engineering-knowledge-guide)

---

## 1. Product Overview & Business Domain

### 1.1 Purpose
The **Enterprise Knowledge & Operations Intelligence Platform** is a dual-intelligence AI platform designed for B2B enterprise operations. Rather than functioning as a standard document chatbot, it bridges the gap between:
1. **Unstructured Knowledge:** Corporate policies, Standard Operating Procedures (SOPs), vendor contracts, operational documentation, and parsed invoices.
2. **Structured Operational Data:** Relational enterprise records (departments, budgets, employee records, vendor details, invoices, and operational expenses).

### 1.2 Enterprise Domain Scope
The platform models a cross-functional enterprise operations environment covering:
* **Procurement & Vendor Management:** Contract compliance, vendor performance, invoice tracking.
* **Corporate Travel & Operational Expenses:** Expense policies, reimbursement limits, operational spending trends.
* **Internal Governance & SOPs:** Compliance audits, policy dissemination, cross-document comparison.

### 1.3 Key Architectural Mandates
* **Deterministic First, Agentic When Justified:** Simple retrieval or database queries follow predictable, low-latency, deterministic paths. Multi-step reasoning across documents and structured data is orchestrated via a controlled state-graph agent.
* **Strict Evidence Grounding & Attribution:** All document insights must provide granular citations (document title, version, page, section heading). All quantitative database insights must expose transparent, read-only SQL queries and source tables.
* **Pre-Retrieval Security Boundaries:** Role-Based Access Control (RBAC) and multi-tenant isolation must occur at the database query level prior to retrieval, preventing unauthorized context leakage.

---

## 2. User Personas & Core Use Cases

| Persona | Primary Goal | Typical Workflows | System Requirements |
| :--- | :--- | :--- | :--- |
| **Business / Operations Analyst** | Audit compliance, identify operational anomalies, verify contract adherence against actual spend. | - "Compare the maximum flight reimbursement policy in the Travel SOP with total flights expensed by Engineering in Q3."<br>- "List all active vendor contracts due for auto-renewal in 60 days alongside their YTD invoiced totals." | - Hybrid RAG + SQL execution.<br>- Cross-document diffing.<br>- SQL query transparency and AST validation. |
| **Enterprise Operations Manager** | High-level decision making, policy review, KPI tracking, and evidence-backed summary generation. | - "Summarize changes between the 2024 and 2025 Information Security Policies."<br>- "Identify departments exceeding 85% of their annual travel budget." | - Executive report generation.<br>- Strict citation backing.<br>- Low-latency single-intent queries. |

---

## 3. System Architecture & Component Topology

The system is implemented as a **Modular Monolith** using **Python and FastAPI**, backed by **PostgreSQL 16 + pgvector**, and instrumented via **Langfuse and OpenTelemetry**.

```text
                                      +---------------------------------------------+
                                      |         Enterprise Web UI / Client          |
                                      +---------------------------------------------+
                                                             |
                                                       HTTPS / JWT
                                                             v
+-------------------------------------------------------------------------------------------------------------------------+
| FASTAPI BACKEND (MODULAR MONOLITH)                                                                                      |
|                                                                                                                         |
|  [ Auth & RBAC Middleware ] ---> [ Ingress Rate Limiter & Audit Logger ] ---> [ Langfuse / OTel Tracing Context ]       |
|                                                                                                                         |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | QUERY DISPATCHER & INTENT ROUTER (Deterministic Classifier)                                                       |  |
|  | - Direct Document Retrieval (RAG Path)                                                                            |  |
|  | - Direct Operational Data Query (SQL Path)                                                                        |  |
|  | - Complex / Multi-step / Hybrid Query (Agent Orchestrator Path)                                                   |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|               |                                         |                                         |                     |
|               v                                         v                                         v                     |
|  +-------------------------+             +-------------------------------+         +-----------------------------+      |
|  | DETERMINISTIC RAG       |             | DETERMINISTIC TEXT-TO-SQL     |         | STATEFUL AGENT ORCHESTRATOR |      |
|  | - Query Rewriting       |             | - Schema Selector             |         | (LangGraph / State Graph)   |      |
|  | - Pre-Retrieval RBAC    |             | - Few-Shot Context Assembly   |         |                             |      |
|  | - Hybrid Search         |             | - SQL Generation (Gemini)     |         | Coordinates:                |      |
|  |   (pgvector + FTS)      |             | - AST Validation & Parser     |         | - RAG Tool                  |      |
|  | - Reciprocal Rank Fusion|             |   (sqlglot - SELECT only)     |         | - SQL Tool                  |      |
|  | - Soft Relevance Filter |             | - Read-Only DB Execution      |         | - Analytics / Python Tool   |      |
|  | - Cross-Encoder Rerank  |             | - Row Limit & Timeout Guard   |         | - Document Compare Tool     |      |
|  | - Citation Generator    |             | - Audit Logging               |         | - Report Synthesizer        |      |
|  +-------------------------+             +-------------------------------+         +-----------------------------+      |
|               \                                         /                                         /                     |
|                \                                       /                                         /                      |
|                 v                                     v                                         v                       |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | MODEL PROVIDER ABSTRACTION LAYER (Ports & Adapters)                                                               |  |
|  | [ BaseLLMProvider ]           [ BaseEmbeddingProvider ]           [ BaseRerankProvider ]                         |  |
|  |        |                                   |                                     |                                |  |
|  |   Gemini Adapter               gemini-embedding-001               FlashRank (Local Cross-Encoder)                 |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------------------------------------------------+
                                                             |
                 +-------------------------------------------+-------------------------------------------+
                 |                                           |                                           |
                 v                                           v                                           v
+----------------------------------+        +----------------------------------+        +----------------------------------+
| PERSISTENCE & VECTOR STORE       |        | ASYNC TASK WORKER                |        | STORAGE ABSTRACTION              |
| PostgreSQL 16 + pgvector         |        | (PostgreSQL SKIP LOCKED Queue)   |        | - Local FileSystem (Dev)         |
| - Relational Business Data (SQL) |        | - Document Parsing & Markdown AST|        | - Cloud Object Storage           |
| - Document Chunks & Embeddings   |        | - Embedding Generation           |        |   (S3 / Supabase / MinIO)        |
| - Users, Roles & Permissions     |        | - Incremental Indexing           |        +----------------------------------+
| - Audit Logs & Session State     |        | - Version Superseding            |
+----------------------------------+        +----------------------------------+
```

---

## 4. Document Intelligence & Ingestion Pipeline

### 4.1 Supported Ingestion Formats
* **PDF:** Text-native PDFs parsed via structural layout analyzers; extensible to OCR (Tesseract/PaddleOCR) for scanned receipts/contracts.
* **DOCX:** Structured XML parsing preserving semantic heading levels (H1, H2, H3) and tables.
* **XLSX / CSV:** Spreadsheet conversion where tabular structures are preserved with prepended column headers per chunk.
* **Markdown / Plain Text:** Direct hierarchical parsing.

### 4.2 Structural & Tabular Parsing Strategy
Standard token-window splitting corrupts tables by severing rows and header-cell relationships. The ingestion pipeline adopts **Structural Parsing**:
1. Documents are first converted into a semantic **Markdown AST**.
2. Tables are extracted as cohesive Markdown units (`| Header 1 | Header 2 |`).
3. Each table chunk is injected with contextual breadcrumbs:
   ```markdown
   [Context: Document "Travel_Policy_2025.pdf" > Section 4.2 "Daily Per Diem Rates"]
   | Tier | Region | Meal Allowance | Incidentals |
   | --- | --- | --- | --- |
   | Tier 1 | North America | $75.00 | $15.00 |
   ```

### 4.3 Versioning, Lineage & Superseding State Machine
Documents follow a strict lifecycle state machine:
$$\text{PENDING} \longrightarrow \text{PROCESSING} \longrightarrow \text{ACTIVE} \longrightarrow \text{SUPERSEDED} \mid \text{ARCHIVED} \mid \text{FAILED}$$

* **Document-Level Permission Source of Truth:** Documents declare `allowed_roles` (e.g., `['admin', 'manager']`). All generated chunks inherit permissions from their parent document.
* **Atomic Version Activation:** When Version $N+1$ finishes chunking and embedding, an atomic database transaction sets Version $N$ to `is_active = FALSE` and `status = 'SUPERSEDED'`, while activating Version $N+1$. Historical chunks remain in the database for auditing and reproducible citations.

---

## 5. Two-Tier Hybrid Retrieval Architecture (RAG)

### 5.1 Retrieval Pipeline Flow
```text
[ User Query + Verified JWT (tenant_id, roles) ]
                        |
                        v
     +-------------------------------------+
     | 1. QUERY REWRITER / EXPANDER        |
     | Generates optimized search queries  |
     +-------------------------------------+
                        |
            +-----------+-----------+
            |                       |
            v                       v
+-----------------------+   +-----------------------+
| Dense Vector (KNN)    |   | Lexical Search (FTS)  |
| gemini-embedding-001  |   | to_tsvector @@ tsquery|
|                       |   |                       |
| HARD PRE-FILTER (SQL):|   | HARD PRE-FILTER (SQL):|
| - tenant_id = :tid    |   | - tenant_id = :tid    |
| - is_active = TRUE    |   | - is_active = TRUE    |
| - embedding_model =   |   | - embedding_model =   |
|   'gemini-emb-001'    |   |   'gemini-emb-001'    |
| - allowed_roles &&    |   | - allowed_roles &&    |
|   :user_roles         |   |   :user_roles         |
+-----------------------+   +-----------------------+
            \                       /
             \                     /
              v                   v
     +-------------------------------------+
     | 2. RECIPROCAL RANK FUSION (RRF)     |
     | Combines ranks: score = 1/(60 + r)  |
     +-------------------------------------+
                        |
                        v
     +-------------------------------------+
     | 3. SOFT RELEVANCE FILTERING         |
     | - Content-hash deduplication        |
     | - Max chunks per single document    |
     | - Minimum similarity thresholds     |
     +-------------------------------------+
                        |
                        v
     +-------------------------------------+
     | 4. CROSS-ENCODER RERANKING          |
     | (FlashRank / local cross-encoder)   |
     | Re-scores query-chunk relevance     |
     +-------------------------------------+
                        |
                        v
     +-------------------------------------+
     | 5. CONTEXT SELECTION & BUDGETING    |
     | - Token budget enforcement          |
     | - "Lost in the middle" reordering   |
     | - Structured citation metadata prep |
     +-------------------------------------+
                        |
                        v
     +-------------------------------------+
     | 6. PROMPT ASSEMBLY & GEMINI LLM     |
     +-------------------------------------+
```

### 5.2 Pre-Retrieval vs. Post-Retrieval Filtering (Security vs. Relevance)
* **Hard Pre-Retrieval Filter (Security Boundary):** Multi-tenancy (`tenant_id`), document status (`is_active = TRUE`), model version (`embedding_model`), and authorization (`allowed_roles && :user_roles`) are executed **inside the PostgreSQL index scan**. This prevents the "Recall Truncation Problem," guaranteeing that every retrieved candidate is legally accessible.
* **Soft Post-Retrieval Filter (Relevance Boundary):** Executed in memory post-RRF to remove duplicate chunks, cap chunks per document, and prune low-confidence results.

---

## 6. Secure Text-to-SQL Architecture

To prevent prompt injection, destructive modifications, and database denial-of-service, Text-to-SQL execution passes through a **5-Gate Defense-in-Depth Layer**:

```text
Natural Language Query
         ↓
[ Gate 1: Minimal Schema Selection ] -> Only relevant table DDL exposed in prompt context
         ↓
[ Gemini LLM ] -> Generates candidate SQL
         ↓
[ Gate 2: AST Parsing (sqlglot) ]   -> Reject non-SELECT, multi-statement queries, comments
         ↓
[ Gate 3: Schema Whitelist Check ]  -> Verify all tables/columns belong to operational schema
         ↓
[ Gate 4: Sandbox Connection Pool ] -> Execute as read-only DB role (enterprise_analyst_ro)
         ↓
[ Gate 5: Execution Guardrails ]    -> Inject LIMIT 100, enforce statement_timeout = 3000ms
         ↓
[ Audit Logging ]                   -> Log query, tokens, execution time, and row count
         ↓
Result Explanation & Visualization
```

---

## 7. Unified Database Schemas & Data Model

All schemas reside in a unified PostgreSQL 16 database.

### 7.1 Unstructured Knowledge & Ingestion Schemas
```sql
CREATE TYPE document_lifecycle_status AS ENUM (
    'PENDING', 'PROCESSING', 'ACTIVE', 'SUPERSEDED', 'ARCHIVED', 'FAILED'
);

-- Documents Table: Master metadata and authorization source of truth
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant',
    title VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    file_hash_sha256 VARCHAR(64) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    status document_lifecycle_status NOT NULL DEFAULT 'PENDING',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_roles TEXT[] NOT NULL DEFAULT '{"admin", "manager", "analyst"}',
    metadata JSONB NOT NULL DEFAULT '{}',
    error_log TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_tenant_active ON documents(tenant_id, is_active);
CREATE INDEX idx_documents_hash ON documents(tenant_id, file_hash_sha256);

-- Document Chunks Table: Chunks inherit permissions; vectors and FTS tokens reside here
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id VARCHAR(64) NOT NULL,
    chunk_index INT NOT NULL,
    
    -- Citation & Source Location Metadata
    page_number INT,
    section_heading VARCHAR(255),
    heading_hierarchy JSONB DEFAULT '[]'::jsonb,
    chunk_type VARCHAR(32) NOT NULL DEFAULT 'text', -- 'text', 'table', 'list'
    table_metadata JSONB DEFAULT '{}'::jsonb,
    char_start_idx INT,
    char_end_idx INT,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    
    -- Hard Security Inheritance
    allowed_roles TEXT[] NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Embedding Model Lineage & Version Segregation
    embedding_model VARCHAR(64) NOT NULL DEFAULT 'gemini-embedding-001',
    embedding_dimension INT NOT NULL DEFAULT 768,
    
    -- Lexical Search Tokens (FTS)
    fts_tokens TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    
    -- Dense Vector Column (768 dimensions)
    embedding VECTOR(768) NOT NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chunks_retrieval_filter ON document_chunks (tenant_id, is_active, embedding_model);
CREATE INDEX idx_chunks_fts ON document_chunks USING GIN(fts_tokens);
CREATE INDEX idx_chunks_vector_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- PostgreSQL-Native Background Queue (SKIP LOCKED)
CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant',
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'QUEUED',
    task_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    error_message TEXT,
    locked_at TIMESTAMPTZ,
    locked_by VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ingestion_jobs_queue ON ingestion_jobs (status, created_at) WHERE status = 'QUEUED';
```

### 7.2 Structured Operational Schemas (Text-to-SQL Target)
```sql
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant',
    code VARCHAR(16) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    annual_budget NUMERIC(14, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id UUID NOT NULL REFERENCES departments(id),
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant',
    employee_code VARCHAR(32) NOT NULL UNIQUE,
    full_name VARCHAR(128) NOT NULL,
    email VARCHAR(128) NOT NULL,
    role_title VARCHAR(128) NOT NULL,
    employment_status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    hire_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant',
    vendor_code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL,
    risk_rating VARCHAR(16) NOT NULL DEFAULT 'LOW',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    associated_document_id UUID REFERENCES documents(id) ON DELETE SET NULL, -- Bridges RAG & SQL
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant',
    contract_number VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    total_value NUMERIC(14, 2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    auto_renew BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    contract_id UUID REFERENCES contracts(id),
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant',
    invoice_number VARCHAR(64) NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    payment_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE operational_expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id UUID NOT NULL REFERENCES departments(id),
    employee_id UUID NOT NULL REFERENCES employees(id),
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant',
    category VARCHAR(64) NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    expense_date DATE NOT NULL,
    description TEXT NOT NULL,
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sql_query_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    user_prompt TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    ast_validation_passed BOOLEAN NOT NULL,
    execution_time_ms NUMERIC(10, 2),
    rows_returned INT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## 8. Architecture Decision Records (ADRs)

### ADR-001: Unified Database — PostgreSQL 16 + pgvector + FTS
* **Decision:** Consolidate transactional entities, vector storage, lexical inverted indexes, and job queues in PostgreSQL 16.
* **Context:** Running dedicated vector stores (e.g., Pinecone/Qdrant) and search engines (Elasticsearch) creates operational overhead and distributed consistency challenges.
* **Consequences:** Single-query joins between RBAC rules, document metadata, and similarity scoring. Eliminates distributed transactions.
* **Migration Trigger:** Evaluate dedicated vector engines if vector count exceeds 10M vectors with high write/query concurrency.

### ADR-002: Model Provider Abstraction (Ports & Adapters)
* **Decision:** Decouple domain logic from LLM vendors using Abstract Base Classes (`BaseLLMClient`, `BaseEmbeddingClient`).
* **Context:** Google Gemini is chosen initially to minimize development and deployment costs. Direct coupling would prevent migrating to OpenAI, Anthropic, or local open-weights models.
* **Consequences:** Vendor quirks are isolated inside `GeminiAdapter`. Switching providers requires updating configuration, not application logic.

### ADR-003: Hybrid Execution — Deterministic Router vs. State Graph
* **Decision:** Implement a two-tiered dispatcher: single-intent queries bypass agents to hit deterministic RAG or SQL pipelines; multi-step hybrid queries route to a State Graph Orchestrator.
* **Context:** Agent loops introduce latency, unpredictable execution paths, and high token costs when applied to simple questions.
* **Consequences:** 80% of enterprise queries execute in sub-second to low-second latency; agents are reserved for genuinely complex multi-step reasoning.

### ADR-004: Ingestion Pipeline with Lineage and Versioning
* **Decision:** Multi-format parser producing Markdown AST with table integrity, chunk lineage, SHA-256 deduplication, and atomic version superseding.
* **Context:** Document updates must not leave outdated chunks retrievable; tabular information must not be severed by token-window boundaries.

### ADR-005: Sandboxed Text-to-SQL Execution Layer
* **Decision:** 5-gate security barrier: minimal schema exposure, `sqlglot` AST validation (SELECT only), whitelist validation, read-only DB role (`enterprise_analyst_ro`), and statement timeouts/row limits.
* **Context:** LLMs cannot be granted direct or write-capable database access due to SQL injection and denial-of-service risks.

### ADR-006: Pre-Retrieval RBAC & Multi-Tenant Boundaries
* **Decision:** Enforce security parameters (`tenant_id`, `is_active`, `allowed_roles`) directly inside the database retrieval query.
* **Context:** In-memory post-filtering causes "Recall Truncation," where unauthorized documents starve the context window of valid documents.

### ADR-007: Embedding Model Lineage & Version Isolation
* **Decision:** Default to `gemini-embedding-001` (768 dimensions), tag every chunk with model version metadata, and filter by `embedding_model = :active_model`.
* **Context:** Mixing vector embeddings from different models in the same distance metric space destroys retrieval recall.

### ADR-008: Document Versioning & Permission Inheritance
* **Decision:** Parent document is the source of truth for ACLs. Chunks inherit permissions upon creation. Atomic status transitions guarantee zero query downtime during re-indexing.

---

## 9. End-to-End Data Flows

### 9.1 Document Ingestion Flow
```text
Upload File (FastAPI)
  ↓ Compute SHA-256 & Store raw file
Insert `documents` row (status = 'PENDING', is_active = FALSE)
  ↓ (Same ACID transaction)
Insert `ingestion_jobs` row (status = 'QUEUED')
  ↓
Background Worker fetches job (`FOR UPDATE SKIP LOCKED`)
  ↓ Parse to Markdown AST (Tables preserved)
Hierarchical Chunking (Metadata: doc_id, version, page, section)
  ↓ Call gemini-embedding-001 (768-dim) in batches
Insert into `document_chunks` (allowed_roles inherited from parent)
  ↓
Atomic Activation Transaction:
  - SET previous_version.status = 'SUPERSEDED', is_active = FALSE
  - SET current_document.status = 'ACTIVE', is_active = TRUE
  - SET current_chunks.is_active = TRUE
  - SET ingestion_job.status = 'COMPLETED'
```

### 9.2 Two-Tier Hybrid Retrieval Flow
```text
User Query + JWT Token
  ↓ Auth Middleware extracts tenant_id and user_roles
Generate 768-dim Query Vector (gemini-embedding-001)
  ↓
PostgreSQL Hard Pre-Filtered Search:
  - Dense: Cosine distance <=> (pgvector)
  - Lexical: ts_rank_cd @@ tsquery (FTS)
  [WHERE tenant_id = :tid AND is_active = TRUE 
   AND embedding_model = :active_model AND allowed_roles && :user_roles]
  ↓
Reciprocal Rank Fusion (RRF): Merge Dense & FTS ranks
  ↓
Soft Relevance Filter: In-memory deduplication and threshold pruning
  ↓
Cross-Encoder Reranking: FlashRank scores top-K candidate chunks
  ↓
Context Selection & Budgeting: Truncate to token limit, format citations
  ↓
Gemini LLM Prompt: Synthesize evidence-grounded answer with source citations
```

### 9.3 Sandboxed Text-to-SQL Execution Flow
```text
User Prompt ("What was Q3 travel spend for Sales?")
  ↓ Intent Router identifies SQL intent
Schema Selector extracts DDL for `departments` and `operational_expenses`
  ↓ Gemini generates candidate SQL query
AST Validation (`sqlglot`):
  - Verify Root == Select
  - Verify Single Statement (No semicolons)
  - Verify Whitelisted Tables only
  - Inject `LIMIT 100` if absent
  ↓
Execute Query on Dedicated Read-Only Pool (`enterprise_analyst_ro`):
  - SET statement_timeout = 3000
  - Execute SQL
  ↓
Record execution details in `sql_query_audit_logs`
  ↓ Gemini synthesizes natural language response + markdown table
```

---

## 10. Observability, Evaluation & Reliability Strategy

### 10.1 Observability Stack
* **Langfuse:** End-to-end tracing for LLM calls, prompts, token counts, latency, and cost attribution per user/tenant.
* **OpenTelemetry:** Distributed tracing across FastAPI endpoints, database queries, and background ingestion jobs.
* **Audit Logs:** Dedicated tables tracking all generated SQL statements and retrieval events.

### 10.2 Evaluation Strategy (Offline Harness & CI/CD)
The system establishes a curated golden dataset of 50 enterprise queries covering:
* **Retrieval Evaluation:** Hit Rate@K, Mean Reciprocal Rank (MRR), and Context Recall.
* **RAG Generation Quality (Ragas / LLM Judge):**
  * *Faithfulness / Groundedness:* Percentage of claims in the answer directly derived from context chunks.
  * *Answer Relevance:* Degree to which the answer directly addresses the user question.
  * *Citation Accuracy:* Precision of page/section citations against ground truth.
* **Text-to-SQL Evaluation:**
  * *AST Validity Rate:* Percentage of generated SQL queries passing `sqlglot` checks.
  * *Execution Accuracy:* Percentage of queries returning non-error results.
  * *Data Ground Truth Match:* Verifying returned rows against pre-calculated SQL fixtures.

---

## 11. Cloud Portability & Free-First Deployment Strategy

The architecture adheres to: **"Free to start, cloud-portable to scale."**

```text
Local Development: Docker Compose
  - FastAPI App
  - PostgreSQL 16 + pgvector
  - Local File Storage

Free Cloud Tier (e.g., Render / Koyeb / Fly.io + Neon / Supabase PostgreSQL):
  - FastAPI Container (512MB RAM target)
  - Managed PostgreSQL (Free tier with pgvector)
  - Lightweight SKIP LOCKED background worker (zero extra containers)

Enterprise Scale (AWS / GCP / Azure):
  - FastAPI on AWS ECS / GCP Cloud Run
  - Managed AWS RDS PostgreSQL with pgvector
  - Storage migrated to AWS S3 (via StorageInterface)
  - Job queue migrated to Redis / Celery or AWS SQS (via JobQueueInterface)
```

---

## 12. Phased Implementation Roadmap

* **Phase 01: Foundation & Contracts** — Completed ✅ (Domain interfaces, configuration, Docker Compose, PostgreSQL + pgvector setup, base abstractions).
* **Phase 02: Auth, RBAC & Multi-Tenancy** — Completed ✅ (JWT authentication, role enforcement, tenant context propagation).
* **Phase 03: Document Ingestion Pipeline** — Completed ✅ (File storage, Markdown AST parsing, chunk lineage, embedding worker, `SKIP LOCKED` job queue).
* **Phase 04: Two-Tier Hybrid Retrieval** — Completed ✅ (FTS + pgvector, Pre-retrieval RBAC filtering, RRF, FlashRank reranking, context selection).
* **Phase 05: Grounded RAG & Citations** — Completed ✅ (Prompt engineering, Gemini adapter, hallucination mitigation, source citation formatting).
* **Phase 06: Secure Text-to-SQL Sandbox** — Completed ✅ (Schema selector, `sqlglot` AST validation, read-only DB role, execution guardrails).
* **Phase 07: Stateful Agent Orchestrator** — Completed ✅ (LangGraph state machine, tool contracts, multi-step RAG + SQL hybrid query workflows).
* **Phase 08: Evaluation & Test Harness** — Completed ✅ (Golden dataset, Ragas retrieval/groundedness testing, SQL validation suite).
* **Phase 09: Observability & Langfuse** — Completed ✅ (Distributed tracing, token tracking, latency instrumentation, audit dashboards).
* **Phase 10: Free Cloud Deployment & CI/CD** — Completed ✅ (Production containerization, GitHub Actions, cloud deployment).

---

## 13. Interview Defense & Engineering Knowledge Guide

### Q1: Why did you choose a Modular Monolith instead of Microservices?
> *"For an enterprise AI platform at this stage, microservices introduce premature distributed complexity: network serialization, distributed transaction failures, deployment overhead, and multi-repo synchronization. By building a Modular Monolith with strict boundary interfaces (Ports and Adapters), we achieve high internal cohesion with low operational complexity. If a specific component like document parsing requires independent auto-scaling later, its clean module interface allows it to be extracted into a standalone service with minimal friction."*

### Q2: Why use PostgreSQL + pgvector instead of a dedicated vector database like Pinecone or Qdrant?
> *"First, it eliminates distributed state. Document metadata, versioning states, RBAC permissions, and relational business records all live in the same ACID-compliant database. Second, it enables true Pre-Retrieval Filtering: we can enforce tenant boundaries and user role permissions in the exact same SQL query that evaluates vector cosine distance. Third, it simplifies operations and keeps hosting free during initial rollout without sacrificing HNSW index performance."*

### Q3: Why is Post-Retrieval Permission Filtering considered an architectural flaw?
> *"Post-retrieval filtering causes Recall Truncation. If you perform an unfiltered Top-K search and 80% of the closest vectors belong to confidential documents the user cannot view, post-filtering strips them out, leaving a starved context window. By pushing RBAC directly into the database query as a hard pre-filter, we guarantee that all K retrieved candidates are authorized for that user."*

### Q4: How do you prevent an LLM from executing destructive SQL?
> *"We implement a 5-gate defense-in-depth model. We never rely on system prompts alone. The query passes through `sqlglot` AST parsing to verify it is strictly a single `SELECT` statement and accesses only whitelisted tables. It executes on an isolated connection pool bound to an unprivileged PostgreSQL user with `GRANT SELECT` only, constrained by a 3-second timeout and an enforced `LIMIT 100` clause."*

### Q5: Why did you implement a Deterministic Router instead of a purely Agentic ReAct loop?
> *"Purely agentic loops are an architectural liability for single-intent tasks due to non-deterministic latency, loop failures, and high token consumption. In enterprise environments, 80% of queries require either direct document search or operational data lookup. We use a deterministic classifier to route these directly at low latency, reserving stateful graph-based agents strictly for hybrid multi-step reasoning."*

### Q6: Why omit Redis from day one and use a PostgreSQL-native queue? How do you prevent the Dual-Write Problem?
> *"Running Redis on free cloud tiers risks 512MB RAM OOM kills. More importantly, direct dual-writes between PostgreSQL and Redis create the Dual-Write Problem (state divergence if one store fails). By using PostgreSQL's `SELECT ... FOR UPDATE SKIP LOCKED`, we achieve true ACID transactional atomicity: document records and ingestion jobs are committed in the exact same transaction. This acts as the natural foundation for the Transactional Outbox Pattern, allowing us to seamlessly swap in Redis or AWS SQS via `BaseJobQueueClient` when scale demands it."*

### Q7: Why use `pyproject.toml` instead of maintaining `requirements.txt`?
> *"Under modern PEP 517/518/621 standards, `pyproject.toml` provides a single declarative source of truth for abstract dependencies, build systems, and development tooling (Ruff, Mypy, Pytest). Maintaining both files manually introduces dependency drift. For production deployments, we generate deterministic lockfiles with `uv` rather than maintaining duplicate manual requirements."*

### Q8: How did you optimize this platform for $0.00/month hosting without sacrificing enterprise reliability?
> *"We designed a zero-cost architecture with zero PyTorch bloat: embedding and LLM generation run on Google Gemini free tier APIs, vector storage with HNSW runs on Neon Serverless PostgreSQL with pgvector, local reranking uses FlashRank ONNX TinyBERT (< 40MB RAM), distributed tracing uses Langfuse Cloud free tier, and the web container runs on Render / Koyeb within a 210MB resident working set—comfortably beneath the 512MB free tier memory ceiling."*


