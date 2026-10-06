# Enterprise RAG & Operations Intelligence Platform

> **A Dual-Intelligence enterprise engine fusing Unstructured Knowledge Bases (PDF, DOCX, TXT, MD) and High-Velocity Relational Business Data (PostgreSQL) into a single, verifiable intelligence layer with zero hallucination.**

---

## 1. System Overview & Problem Statement

Modern enterprise intelligence is divided into two disconnected silos:
1. **Unstructured Knowledge**: Company policies, compliance guidelines, vendor master agreements, statement of work (SOW) documents, and standard operating procedures (SOPs).
2. **Structured Operational Data**: Relational transactional tables tracking departmental budgets, active employee rosters, vendor contracts, accounts payable invoices, and operational expenses.

Traditional RAG architectures fail when faced with questions that require cross-referencing qualitative rules against quantitative operational numbers. For example:
> *"Audit all Q3 engineering travel claims against our standard travel policy and highlight any reimbursements exceeding meal or lodging limits."*

A standard vector database cannot compute financial aggregations across thousands of relational rows. Conversely, a relational database cannot interpret policy exceptions defined in an uploaded PDF.

**This platform resolves the divide with a Dual-Intelligence architecture:**
- **Zero-Latency Intent Routing**: Heuristic regex pre-classification (~0ms) with document-catalog awareness, falling back to a schema-grounded LLM router for ambiguous requests.
- **Two-Tier Hybrid Document Retrieval**: pgvector dense semantic search (768-dim embeddings) fused with native PostgreSQL Full-Text Search (TSVECTOR + GIN) via Reciprocal Rank Fusion ($k=60$), re-ranked with a local ONNX cross-encoder (`ms-marco-TinyBERT-L-2-v2`).
- **5-Gate Defense-in-Depth SQL Sandbox**: AST verification via `sqlglot`, strict read-only execution, schema whitelisting, prohibited function screening, automated multi-tenant filter injection, and hard query limits.
- **Stateful Multi-Agent Orchestration**: LangGraph-powered directed acyclic graph (DAG) with concurrent parallel execution (`asyncio.gather`) for hybrid audit workflows.
- **Micro-Batch Ingestion Pipeline**: Asynchronous PostgreSQL queue (`FOR UPDATE SKIP LOCKED`) with automatic rate-limit throttling and atomic document version superseding.

---

## 2. Architecture & System Topologies

### 2.1 High-Level Architecture

```mermaid
flowchart TB
    subgraph ClientLayer["Frontend Studio (Next.js 16 + React 19)"]
        UI_Chat["Unified Chat Console"]
        UI_RAG["Policy & Document RAG"]
        UI_SQL["Text-to-SQL Studio"]
        UI_Ingest["Document Ingestion Hub"]
        UI_Trace["Agent Trace Inspector"]
    end

    subgraph APILayer["FastAPI Enterprise Gateway (Python 3.12)"]
        AuthMid["JWT Auth & Multi-Tenant Isolation (RBAC)"]
        RouterSvc["Dual-Stage Query Intent Router"]
    end

    subgraph IntelligenceEngines["Core Intelligence Engines"]
        subgraph UnstructuredPipeline["Unstructured Document Intelligence"]
            DocParser["Markdown AST Parser (PDF, DOCX, TXT, MD)"]
            Embedder["Micro-Batch Embedder (gemini-embedding-001, 768-dim)"]
            Retriever["Hybrid Retrieval (Dense pgvector + Sparse TSVECTOR)"]
            RRF["Reciprocal Rank Fusion (k=60)"]
            Reranker["FlashRank Cross-Encoder (TinyBERT ONNX)"]
            RAGSvc["Grounded Generator with Citation Lineage"]
        end

        subgraph StructuredPipeline["Structured Operational Intelligence"]
            TextToSQL["Text-to-SQL Generator (gemini-3.5-flash-lite)"]
            SQLSandbox["5-Gate SQL AST Sandbox (sqlglot)"]
            ReadOnlyExec["Read-Only Transaction Executor (3000ms Timeout)"]
            AuditLogger["Persistent Query Audit Logger"]
        end

        subgraph AgentCoordinator["LangGraph Stateful Orchestrator"]
            Planner["Query Decomposer & Planner"]
            ParallelNode["Concurrent Worker (asyncio.gather)"]
            Synthesizer["Executive Synthesis Engine"]
        end
    end

    subgraph DataLayer["Enterprise PostgreSQL 16 + pgvector"]
        DB_Docs[("documents & document_chunks (GIN & HNSW)")]
        DB_Queue[("ingestion_jobs (SKIP LOCKED Queue)")]
        DB_Ops[("Operational Business Tables\n(departments, employees, vendors,\ncontracts, invoices, expenses)")]
        DB_Audit[("sql_query_audit_logs")]
    end

    ClientLayer -->|REST / SSE Tokens| APILayer
    APILayer --> AuthMid
    AuthMid --> RouterSvc
    RouterSvc -->|RAG Route| UnstructuredPipeline
    RouterSvc -->|SQL Route| StructuredPipeline
    RouterSvc -->|HYBRID Route| AgentCoordinator

    AgentCoordinator --> Planner
    Planner --> ParallelNode
    ParallelNode -->|Concurrent Branch 1| Retriever
    ParallelNode -->|Concurrent Branch 2| TextToSQL
    Retriever --> RRF --> Reranker --> RAGSvc
    TextToSQL --> SQLSandbox --> ReadOnlyExec --> AuditLogger
    ParallelNode --> Synthesizer

    UnstructuredPipeline --> DB_Docs
    DocParser --> DB_Queue
    ReadOnlyExec --> DB_Ops
    AuditLogger --> DB_Audit
```

---

### 2.2 LangGraph Orchestrator Execution Flow

When a user submits a query requiring both document policies and operational numbers, the orchestrator executes concurrently rather than sequentially, reducing execution latency from ~35s down to ~15s:

```mermaid
stateDiagram-v2
    [*] --> Planner: User Natural Language Query

    state Planner {
        direction TB
        Classify: Intent Classification (Fast Heuristic / LLM)
        Decompose: Break query into document_question & database_question
    }

    Planner --> DecisionRoute

    state DecisionRoute <<choice>>
    DecisionRoute --> RAG_Branch: Route == RAG
    DecisionRoute --> SQL_Branch: Route == SQL
    DecisionRoute --> Concurrent_Branch: Route == HYBRID_AGENT

    state Concurrent_Branch {
        direction LR
        state "asyncio.gather()" as Gather {
            state "RAG Worker Node" as RAGNode {
                DenseSparse: Vector + FTS Search
                RRF_Step: Reciprocal Rank Fusion
                FlashRank: ONNX Cross-Encoder
                ExtractContext: Build Context Chunks
            }
            state "SQL Worker Node" as SQLNode {
                GenSQL: Text-to-SQL Translation
                Sandbox: 5-Gate AST Validation & Tenant Injection
                Execute: Read-Only Query Run (<3000ms)
            }
        }
    }

    state RAG_Branch {
        RAGOnly: Full RAG Search & Generation
    }

    state SQL_Branch {
        SQLOnly: Text-to-SQL + Sandbox + Explanation
    }

    Concurrent_Branch --> Synthesizer: Merged State (Citations + Tabular Rows)
    RAG_Branch --> Synthesizer
    SQL_Branch --> Synthesizer

    state Synthesizer {
        CompareRules: Cross-reference document rules with actual figures
        DetectViolations: Explicitly highlight policy discrepancies / budget overruns
        DraftBriefing: Produce executive-ready briefing
    }

    Synthesizer --> [*]: Final Response with Structured Citations & Table Preview
```

---

### 2.3 Two-Tier Hybrid Retrieval & Re-ranking Pipeline

```mermaid
flowchart LR
    Query["User Question"] --> Embed["Query Embedding\n(gemini-embedding-001)"]
    
    subgraph CandidateRetrieval["Tier 1: Parallel Candidate Search (top_k = 20)"]
        Embed -->|Vector Cosine Distance| Dense["Dense Search\npgvector <=> operator\n+ Tenant & RBAC Filter"]
        Query -->|English Stemmed Tsquery| Sparse["Sparse Search\nFTS tokens @@ operator\n+ Tenant & RBAC Filter"]
    end

    Dense --> RRF["Reciprocal Rank Fusion\nScore = 1/(60 + Rank_dense) + 1/(60 + Rank_sparse)"]
    Sparse --> RRF

    subgraph DeepRerank["Tier 2: Neural Cross-Encoder & Window Reordering"]
        RRF --> CrossEncoder["FlashRank Local ONNX\n(ms-marco-TinyBERT-L-2-v2)\nComputes query-chunk cross-attention"]
        CrossEncoder --> Pruning["Score Thresholding & Token Budget Cap"]
        Pruning --> LostInMiddle["Lost-in-the-Middle Edge Distribution\nPlaces highest-scoring items at\nstart and end of prompt"]
    end

    LostInMiddle --> FinalContext["Grounded Prompt Context Blocks\nwith Source IDs [1], [2]..."]
```

---

### 2.4 5-Gate Defense-in-Depth SQL AST Sandbox

To safely execute dynamic LLM-generated SQL against business data without risk of data destruction, SQL injection, or cross-tenant leakage, all generated SQL must pass through five rigorous validation gates:

```mermaid
flowchart TD
    RawSQL["Candidate SQL from LLM"] --> Gate1["Gate 1: Markdown Stripping & Format Cleanup"]
    Gate1 --> Gate2["Gate 2: AST Parser (sqlglot)\n- Exactly one statement allowed\n- Root node MUST be exp.Select (rejection of INSERT, UPDATE, DROP, ALTER)"]
    Gate2 -->|Violation| Blocked["Raise SQLSecurityViolation & Log to Audit Table"]
    Gate2 -->|Valid SELECT| Gate3["Gate 3: Whitelist & Prohibited Functions\n- Tables must be in: {departments, employees, vendors, contracts, invoices, operational_expenses}\n- Block system functions: pg_sleep, pg_read_file, current_user, inet_client_addr, etc."]
    Gate3 -->|Violation| Blocked
    Gate3 -->|Approved Schema| Gate4["Gate 4: AST Multi-Tenant Injection\n- Traverses all referenced tables\n- Injects: alias.tenant_id = :tenant_id into WHERE clause"]
    Gate4 --> Gate5["Gate 5: Query Limit Enforcement\n- Appends LIMIT 100 or clamps existing limit <= 100"]
    Gate5 --> ExecEnv["Read-Only Execution Sandbox\n- SET statement_timeout = 3000ms\n- SET TRANSACTION READ ONLY\n- Automatic rollback to keep session write-capable"]
    ExecEnv --> Audit["Commit Entry to sql_query_audit_logs"]
    Audit --> Return["Return Column Headers, Serialized Rows, Exec Time"]
```

---

## 3. Technology Stack & Verification

Every component listed below is verified in the codebase:

| Subsystem | Component / Library | Implementation Details |
| :--- | :--- | :--- |
| **Backend Runtime** | Python 3.12 + FastAPI 0.110+ | Asynchronous REST gateway with dependency injection, lifespan management, and CORS middleware |
| **Relational Database** | PostgreSQL 16 + `pgvector` 0.2.5+ | Vector indexes, full-text search indexes (`GIN` on `tsvector`), and operational business tables |
| **ORM & Async DB Driver** | SQLAlchemy 2.0+ & `asyncpg` 0.29+ | Async connection pooling, `selectinload` relationship loading, transaction isolation |
| **Embedding Model** | `gemini-embedding-001` via `google-genai` | 768 dimensions, specialized task types (`RETRIEVAL_DOCUMENT` and `RETRIEVAL_QUERY`) |
| **Primary LLM** | `gemini-3.5-flash-lite` | Grounded generative RAG, zero-temperature Text-to-SQL translation, and multi-agent synthesis |
| **Re-ranking Engine** | `flashrank` 0.2+ | `ms-marco-TinyBERT-L-2-v2` ONNX cross-encoder model running locally on CPU in async threadpools |
| **SQL AST Engine** | `sqlglot` 23.0+ | Transpilation, AST syntax tree analysis, table extraction, and tenant filter mutation |
| **Document Parsers** | `pypdf` 4.0+ & `python-docx` 1.1+ | Structural parsing, heading hierarchy extraction, and automated Word table to Markdown table conversion |
| **Agent Framework** | `langgraph` 0.2+ & `langchain-core` | `StateGraph` directed acyclic execution graph with parallel branch gathering |
| **Observability** | `langfuse` 2.0+ (Optional) | End-to-end trace collection, span tracking, token generation logging with no-op `NullSpan` fallback |
| **Authentication** | `pyjwt` 2.8+ & `bcrypt` 4.1+ | Multi-tenant JWT bearer tokens (HS256, 24-hour expiration) and password hashing |
| **Frontend Framework** | Next.js 16.3.7 (Turbopack) + React 19.2 | Client-side reactive UI with modular tab views, Lucide icons, and zero third-party UI framework lock-in |

---

## 4. Database Architecture & Schema Specification

The database contains two functional domains:
1. **Document Management & Ingestion Queues** (Unstructured Knowledge)
2. **Operational Enterprise Tables** (Structured Business Operations)

### 4.1 Document & Knowledge Tables
- `users`: Multi-tenant user identities with roles (`ADMIN`, `MANAGER`, `ANALYST`) and hashed passwords.
- `documents`: Document registry tracking original filenames, SHA-256 hashes, storage paths, MIME types, versions, lifecycle states (`PENDING`, `PROCESSING`, `ACTIVE`, `SUPERSEDED`, `ARCHIVED`, `FAILED`), and access control arrays (`allowed_roles`).
- `document_chunks`: Structural chunk blocks containing page numbers, section headings, heading hierarchy paths, chunk types (`text`, `table`), table dimensions, `content`, 768-dimensional `embedding` vector, and computed `fts_tokens` (`tsvector`) for full-text search.
- `ingestion_jobs`: Transactional job queue supporting atomic concurrency using `FOR UPDATE SKIP LOCKED`.

### 4.2 Operational Relational Tables
- `departments`: Department codes (`ENG`, `MKT`, `FIN`, `HR`, `SEC`), names, and annual allocated budgets.
- `employees`: Employee identifiers, department foreign keys, full names, corporate emails, role titles, employment statuses (`ACTIVE`, `TERMINATED`), and hire dates.
- `vendors`: Approved third-party vendors with category classifications (`Software`, `Logistics`, `Consulting`, `Facilities`), risk ratings (`LOW`, `MEDIUM`, `HIGH`), and active flags.
- `contracts`: Vendor master contracts with associated document IDs, contract values, validity date ranges, and renewal terms.
- `invoices`: Invoices linked to contracts and vendors, tracking amounts, payment statuses (`PENDING`, `PAID`, `OVERDUE`), due dates, and settlement timestamps.
- `operational_expenses`: Granular employee expenditure records with expense categories (`Travel`, `Software`, `Supplies`, `Meals`), amounts, approval flags, and dual foreign keys to employees and departments.
- `sql_query_audit_logs`: Immutable audit trails logging user queries, raw generated SQL, sanitized SQL, execution durations, row counts, and error messages.

---

## 5. API Reference & Verification Guide

The backend exposes clean, versioned endpoints under `/api/v1/`.

### 5.1 Authentication Endpoints

#### Register a New User
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "analyst@enterprise.com",
    "password": "SecurePassword123!",
    "full_name": "Senior Operations Analyst",
    "tenant_id": "default_tenant",
    "role": "analyst"
  }'
```

#### User Login & Token Generation
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@gmail.com",
    "password": "Admin@12345",
    "tenant_id": "default_tenant"
  }'
```
*Response returns a signed JWT `access_token` and user profile.*

---

### 5.2 Document Ingestion Endpoints

#### Upload and Enqueue Document
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -F "file=@sample_documents/company_travel_policy.pdf" \
  -F "title=Company Travel & Expense Policy 2026" \
  -F "allowed_roles=admin,manager,analyst"
```

#### Check Document Processing Status
```bash
curl -X GET "http://localhost:8000/api/v1/documents/<DOCUMENT_UUID>/status" \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>"
```

---

### 5.3 Hybrid Search & Grounded RAG Endpoints

#### Two-Tier Hybrid Search (Dense + Sparse + RRF + Cross-Encoder)
```bash
curl -X POST "http://localhost:8000/api/v1/retrieval/search" \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the reimbursement limits for international flight travel?",
    "top_k": 20,
    "top_n": 5,
    "score_threshold": 0.0,
    "max_tokens": 4000
  }'
```

#### Grounded RAG with Citation Lineage
```bash
curl -X POST "http://localhost:8000/api/v1/rag/ask" \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the maximum daily per diem meal allowance for domestic travel?",
    "top_k": 20,
    "top_n": 5,
    "temperature": 0.0
  }'
```

#### Real-Time SSE Token Streaming
```bash
curl -N -X POST "http://localhost:8000/api/v1/rag/stream" \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Summarize the termination clauses in our software vendor contracts."
  }'
```

---

### 5.4 Text-to-SQL & Operational Data Endpoints

#### Execute Natural Language SQL Query
```bash
curl -X POST "http://localhost:8000/api/v1/sql/query" \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "List the top 3 departments with the highest total operational expenses this year",
    "explain": true
  }'
```

#### Inspect SQL Security Audit Logs
```bash
curl -X GET "http://localhost:8000/api/v1/sql/audit-logs?limit=10" \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>"
```

---

### 5.5 Stateful Multi-Agent Endpoint

#### Unified Enterprise Agent Query
```bash
curl -X POST "http://localhost:8000/api/v1/agent/query" \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compare our official travel policy daily meal allowance with actual meal expense claims in the Engineering department to identify any non-compliant transactions.",
    "force_route": null
  }'
```
*Dispatches intent, invokes RAG and SQL concurrently via LangGraph, and synthesizes findings into an executive report with citation lineage and raw SQL records.*

---

### 5.6 Administration & Demo Seeding

#### Trigger Database Seeding via HTTP
```bash
curl -X POST "http://localhost:8000/api/v1/admin/seed"
```
*Idempotently seeds the administrator account and all relational demonstration entities.*

---

## 6. Getting Started & Local Development

### 6.1 Prerequisites
- Python 3.12+
- Node.js 20+ & npm
- PostgreSQL 16 with the `pgvector` extension enabled
- Google Gemini API Key

### 6.2 Environment Configuration
Create a `.env` file in the project root:

```env
# Application Settings
PROJECT_NAME="Enterprise RAG & Operations Intelligence"
ENVIRONMENT="development"
DEBUG=true

# Database Configuration
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_rag"

# Google Gemini API
GEMINI_API_KEY="your-gemini-api-key"
ACTIVE_EMBEDDING_MODEL="gemini-embedding-001"
EMBEDDING_DIMENSION=768
ACTIVE_LLM_MODEL="gemini-3.5-flash-lite"

# Security & Multi-Tenancy
JWT_SECRET_KEY="generate-a-secure-random-32-byte-hex-string"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Observability (Optional)
LANGFUSE_ENABLED=false
```

### 6.3 Local Installation & Execution

#### Backend Setup
```bash
# 1. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -e .

# 3. Seed operational business demo data
python scripts/seed_operational_data.py

# 4. Start the FastAPI development server
uvicorn src.main:app --reload --port 8000
```

#### Frontend Setup
```bash
# 1. Navigate to frontend workspace
cd frontend

# 2. Install dependencies
npm install

# 3. Launch Next.js Turbopack development server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to access the interactive web console.

#### Default Demo Credentials
- **Username / Email**: `admin@gmail.com`
- **Password**: `Admin@12345`
- **Role**: `ADMIN`
- **Tenant ID**: `default_tenant`

---

## 7. Production Deployment

### 7.1 Single-Container Embedded Worker Architecture
In traditional deployments, background queues require dedicated Redis instances, Celery workers, and separate worker containers.

This project implements an **embedded worker pattern** within the FastAPI lifespan (`src/main.py`). The application runs both the HTTP server and the asynchronous ingestion worker (`IngestionWorker`) concurrently inside a single container under 512MB RAM, along with an autonomous orphaned-job sweeper that unlocks stalled jobs after 60 minutes.

### 7.2 Docker Compose Deployment
Run the full production stack locally with a single command:

```bash
docker compose up -d --build
```

### 7.3 Render Blueprint (100% Free Tier Deployment)
The repository includes a ready-to-use [`render.yaml`](./render.yaml) blueprint configuring:
1. **Managed PostgreSQL Database** (Free Tier with vector support)
2. **FastAPI Web Service** (Built from [`Dockerfile`](./Dockerfile) with embedded worker and `AUTO_SEED=true`)
3. **Next.js Web Service** (Built from `./frontend` running Node.js)

To deploy:
1. Push this repository to GitHub.
2. In the Render Dashboard, select **New > Blueprint**.
3. Link your repository. Render will automatically configure services and start deployment.
4. Set your `GEMINI_API_KEY` in the environment settings.
5. Log in with the default admin credentials once the build finishes.

---

## 8. Evaluation & Quality Metrics

The platform includes an automated evaluation harness in `scripts/run_evaluation.py` and `src/services/evaluation.py`:

```bash
python scripts/run_evaluation.py
```

The evaluation suite validates three key dimensions:
1. **Deterministic Retrieval Accuracy**: Evaluates Hit Rate@1, Hit Rate@3, Hit Rate@5, and Mean Reciprocal Rank (MRR).
2. **Model-as-a-Judge Groundedness**: Uses a zero-temperature LLM judge to compute claim-level faithfulness scores and detect unsupported assertions.
3. **SQL AST & Schema Validation**: Verifies that generated SQL queries parse to clean AST representations, reference only whitelisted tables, and match golden target columns.
