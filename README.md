# Enterprise RAG & Operations Intelligence Platform

> **A Dual-Intelligence enterprise engine fusing Unstructured Knowledge Bases (PDF, DOCX, TXT, MD) and High-Velocity Relational Business Data (PostgreSQL) into a single, verifiable intelligence layer with zero hallucination.**

---

## 1. Problem

Modern enterprise data architectures are fractured into two isolated silos:

```
┌────────────────────────────────────────────────────────┐   ┌────────────────────────────────────────────────────────┐
│           UNSTRUCTURED KNOWLEDGE BASES                 │   │            STRUCTURED OPERATIONAL DATA                 │
│                                                        │   │                                                        │
│ • Corporate Travel & Expense Policies                  │   │ • Departmental Budgets (departments)                   │
│ • Vendor Master Service Agreements (MSAs)              │   │ • Active Employee Rosters (employees)                  │
│ • Statements of Work (SOWs) & SLAs                     │   │ • Approved Vendor Database (vendors)                   │
│ • Standard Operating Procedures (SOPs)                 │   │ • Executed Contracts (contracts)                       │
│ • HR Employee Handbooks & Compliance Guidelines        │   │ • Accounts Payable Invoices (invoices)                 │
│                                                        │   │ • Transactional Expenses (operational_expenses)        │
└────────────────────────────────────────────────────────┘   └────────────────────────────────────────────────────────┘
```

### Why Existing Approaches Fail

1. **Standard Vector RAG Fails on Operations**:
   Vector databases excel at fuzzy textual similarity, but they cannot perform deterministic mathematical aggregations, groupings, or joins across thousands of operational records. A query like *"Total unpaid invoices across all active logistics vendors"* cannot be answered reliably by embedding invoice PDFs into a vector space.

2. **Text-to-SQL Fails on Policies & Contracts**:
   Text-to-SQL engines excel at generating relational queries, but they have zero visibility into qualitative business rules, clause exceptions, or compliance limits locked inside PDFs or Word documents. A query like *"What is the approved daily dinner allowance in Tier-1 cities?"* does not exist in relational tables.

3. **The Multi-Step Compliance Gap**:
   Real-world executive inquiries routinely require **both** sources simultaneously:
   > *"Audit all Q3 engineering travel claims against our standard travel policy and highlight any reimbursements exceeding meal or lodging limits."*

Answering this requires extracting the qualitative policy rule from an unstructured document, translating the data audit into a sandboxed relational SQL query, and cross-referencing both outputs to identify policy breaches.

---

## 2. Architecture

The platform implements a **Dual-Intelligence Architecture** orchestrated by a unified query router, stateful agent graphs, and isolated execution pipelines.

### 2.1 System Topology

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
        AuthMid["JWT Auth & Multi-Tenant RBAC Boundary"]
        RouterSvc["Dual-Stage Query Intent Router"]
    end

    subgraph IntelligenceEngines["Core Intelligence Engines"]
        subgraph UnstructuredPipeline["Unstructured Document Intelligence"]
            DocParser["Markdown AST Parser (PDF, DOCX, TXT, MD)"]
            Embedder["Micro-Batch Embedder (gemini-embedding-001, 768-dim)"]
            Retriever["Two-Tier Hybrid Search (Dense pgvector + Sparse TSVECTOR)"]
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
            Planner["Query Decomposer & Sub-Query Planner"]
            ParallelNode["Concurrent Worker (asyncio.gather)"]
            Synthesizer["Executive Synthesis Engine"]
        end
    end

    subgraph DataLayer["Enterprise PostgreSQL 16 + pgvector"]
        DB_Docs[("documents & document_chunks\n(GIN fts_tokens + Cosine Vector)")]
        DB_Queue[("ingestion_jobs\n(SKIP LOCKED Queue)")]
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

### 2.2 Core Architectural Principles

- **Zero-Trust Multi-Tenancy**: Every database query—whether semantic vector similarity, full-text lexical search, or generated SQL—is strictly pre-filtered by `tenant_id` and verified against caller RBAC roles (`ADMIN`, `MANAGER`, `ANALYST`).
- **Zero Hallucination with Lineage**: Every statement generated by RAG is linked to a deterministic numbered citation bracket (`[1]`, `[2]`), mapping directly to the source document, page number, section heading, and verbatim text snippet.
- **Embedded Ingestion Worker**: Eliminates external Celery/Redis dependencies. Ingestion tasks run asynchronously inside the FastAPI lifespan using PostgreSQL `FOR UPDATE SKIP LOCKED`, keeping the entire service operational under 512MB RAM for free-tier deployments.

---

## 3. Tech Stack

Every technology in this stack is verified directly against the production codebase:

| Category | Technology | Version | Purpose in Architecture |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | FastAPI | `0.110+` | High-performance asynchronous REST API gateway and SSE token streaming |
| **Runtime** | Python | `3.12` | Core backend language with native async/await and strict type hinting |
| **Database & Search** | PostgreSQL 16 + `pgvector` | `0.2.5+` | Unified database for relational entities, dense vector search, and full-text TSVECTOR indexing |
| **ORM & Driver** | SQLAlchemy + `asyncpg` | `2.0+` / `0.29+` | Async connection pooling, `selectinload` relationship loading, transaction isolation |
| **Embedding Model** | `gemini-embedding-001` | Cloud API | 768-dimensional semantic embeddings for document chunks and search queries |
| **Primary LLM** | `gemini-3.5-flash-lite` | Cloud API | Intent routing, Text-to-SQL translation, grounded RAG answering, and multi-agent synthesis |
| **Cross-Encoder Reranker** | FlashRank (`ms-marco-TinyBERT-L-2-v2`) | `0.2+` | Local ONNX cross-encoder running CPU-side for deep semantic query-passage re-ranking |
| **SQL AST Engine** | `sqlglot` | `23.0+` | AST parsing, dialect transpilation, safety gate validation, and multi-tenant filter injection |
| **Document Parsers** | `pypdf` + `python-docx` | `4.0+` / `1.1+` | Structural parsing for PDF, DOCX (with table-to-Markdown conversion), TXT, and Markdown |
| **Agent Orchestration** | `langgraph` + `langchain-core` | `0.2+` | Stateful DAG orchestration with parallel branch execution (`asyncio.gather`) |
| **Authentication** | `pyjwt` + `bcrypt` | `2.8+` / `4.1+` | JWT bearer token issuing (`HS256`, 24h expiration) and secure password hashing |
| **Frontend Framework** | Next.js 16 (Turbopack) | `16.3.7` | Production React 19 app with modular studio interfaces, SSE streaming, and Lucide icons |
| **Observability** | Langfuse (Optional) | `2.0+` | Distributed tracing with automated fallback to zero-overhead local `NullSpan` |

---

## 4. RAG Pipeline

The unstructured document pipeline enforces end-to-end provenance—from initial upload to grounded citation generation.

```mermaid
flowchart TD
    subgraph IngestionStage["1. Ingestion & Versioning"]
        Upload["File Upload (PDF, DOCX, TXT, MD)"] --> ASTParse["DocumentParser\nExtracts headings, paragraphs, converts docx tables to Markdown"]
        ASTParse --> JobQueue["PostgreSQL Ingestion Queue\n(status: QUEUED, SKIP LOCKED)"]
        JobQueue --> MicroBatch["Micro-Batch Embedder\n5 chunks/batch with dynamic cool-down delays"]
        MicroBatch --> Supersede["Atomic Versioning Transaction\nOld active versions marked SUPERSEDED\nNew chunks set to ACTIVE with RBAC inheritance"]
    end

    subgraph TwoTierRetrieval["2. Two-Tier Hybrid Retrieval"]
        UserQuery["User Query"] --> EmbedQuery["Embed Query Vector\n(gemini-embedding-001, 768-dim)"]
        EmbedQuery --> DenseSearch["Dense Cosine Search\npgvector <=> operator\nWHERE tenant_id = :id AND role = ANY(allowed_roles)"]
        UserQuery --> SparseSearch["Sparse Lexical Search\nPostgreSQL fts_tokens @@ plainto_tsquery()\nWHERE tenant_id = :id AND role = ANY(allowed_roles)"]
        DenseSearch --> RRF["Reciprocal Rank Fusion (k=60)\nRRF_Score = 1/(60 + Rank_dense) + 1/(60 + Rank_sparse)"]
        SparseSearch --> RRF
        RRF --> FlashRank["FlashRank Cross-Encoder\n(ms-marco-TinyBERT-L-2-v2)\nLocal ONNX async scoring"]
        FlashRank --> LostInMiddle["Lost-in-the-Middle Edge Reordering\nPlaces top-ranked passages at start/end of prompt"]
    end

    subgraph GroundedGeneration["3. Grounded Generation & Citation Lineage"]
        LostInMiddle --> PromptBuild["Context Assembly with Numbered Headers\n[1] Document: Policy | Section: Travel..."]
        PromptBuild --> LLMGen["Gemini 3.5 Flash Lite\nStrict System Instruction: Ground answers ONLY in sources"]
        LLMGen --> CitExtract["Citation Extractor\nRegex parses [N] brackets, verifies existence in source map"]
        CitExtract --> Output["RAGQueryResponse\nAnswer text + structured CitationItem array"]
    end
```

### Key RAG Implementation Details

1. **Table-Aware Markdown AST Parsing (`src/services/parser.py`)**:
   - Parses DOCX files block-by-block. Native Word tables (`tbl`) are automatically transformed into clean GitHub-Flavored Markdown tables with structured headers and rows (`| Col 1 | Col 2 |`), preserving relational layouts for the LLM.
2. **Rate-Limit Resilient Micro-Batching (`src/services/ingestion.py`)**:
   - Ingestion chunks are dispatched in micro-batches of 5 chunks with exponential backoff and dynamic cool-down delays, preventing quota exhaustion (`ResourceExhausted 429`) on free-tier LLM endpoints.
3. **Atomic Document Superseding**:
   - When a document with an existing filename is uploaded into the same tenant, the database atomically marks previous versions as `SUPERSEDED`, deactivates their chunks (`is_active = false`), and activates the new version within a single transaction.
4. **Citation Lineage Guarantee**:
   - Bracket citations (`[1]`, `[2]`) in generated responses are validated against the actual retrieved chunks. If the retrieved context is insufficient, the system returns a deterministic disclaimer rather than speculating.

---

## 5. Agent Workflow

For complex queries requiring cross-referencing between policy documents and operational databases, the platform uses a **LangGraph-driven Stateful Agent Graph**.

### 5.1 Orchestration Topology

```mermaid
flowchart TD
    START([START]) --> Planner["Planner Node\nDecomposes user query into:\n• document_question (RAG)\n• database_question (SQL)"]
    
    Planner --> ConditionalRoute{Route Classification}
    
    ConditionalRoute -->|RAG| RAGOnly["RAG Worker Node"]
    ConditionalRoute -->|SQL| SQLOnly["SQL Worker Node"]
    ConditionalRoute -->|HYBRID_AGENT| ParallelNode["Parallel Execution Node\nasyncio.gather(RAGNode, SQLNode)"]

    subgraph ConcurrentExecution["Concurrent Branch (HYBRID_AGENT)"]
        ParallelNode --> BranchRAG["RAG Search & Retrieval\n(Hybrid + FlashRank)"]
        ParallelNode --> BranchSQL["Text-to-SQL + Sandbox\n(5 Gates + Read-Only Exec)"]
        BranchRAG --> GatherMerge["Merge Plan Steps & Results\n(Isolated Exception Handling)"]
        BranchSQL --> GatherMerge
    end

    GatherMerge --> Synthesizer["Synthesizer Node\nCross-references policy rules with actual figures\nHighlights non-compliant claims & budget overruns"]
    RAGOnly --> Synthesizer
    SQLOnly --> Synthesizer

    Synthesizer --> END([END])
```

### 5.2 Concurrency Optimization
In hybrid execution mode, rather than running RAG search and Text-to-SQL sequentially (which takes ~35 seconds), the `_parallel_rag_sql_node` executes both tasks concurrently using Python's `asyncio.gather()`:

```python
# Concurrently dispatches independent retrieval and database tasks
rag_result, sql_result = await asyncio.gather(
    self._rag_node(state, config),
    self._sql_node(state, config),
    return_exceptions=True,  # Error isolation: one failure does not crash the pipeline
)
```

**Result**: Hybrid query latency drops from ~35s down to **~15–20s**, with isolated exception handling so the synthesizer can still deliver partial findings if one branch experiences issues.

---

## 6. Text-to-SQL Safeguards

Allowing an LLM to generate raw SQL against an operational database requires defense-in-depth security. The platform implements a **5-Gate AST Validation Sandbox** via `sqlglot`:

```mermaid
flowchart TD
    RawSQL["Raw SQL Generated by LLM"] --> Gate1["Gate 1: Markdown Sanitizer\nRemoves codeblocks (```sql ... ```) and leading/trailing whitespace"]
    
    Gate1 --> Gate2["Gate 2: AST Parser & Statement Count\n• sqlglot.parse(read='postgres')\n• Enforces exactly 1 statement (blocks multi-query injection)\n• Verifies root AST is exp.Select (rejects INSERT, UPDATE, DELETE, DROP, ALTER)"]
    
    Gate2 -->|Violation| Reject["Raise SQLSecurityViolation\nRecord to sql_query_audit_logs with status=BLOCKED"]
    
    Gate2 -->|Pass| Gate3["Gate 3: Whitelist & Prohibited Functions\n• Tables must belong to: {departments, employees, vendors, contracts, invoices, operational_expenses}\n• Blocks system functions: pg_sleep, pg_read_file, current_user, inet_client_addr, etc."]
    
    Gate3 -->|Violation| Reject
    
    Gate3 -->|Pass| Gate4["Gate 4: Multi-Tenant AST Injection\n• Iterates through all referenced tables/aliases in AST\n• Injects: WHERE alias.tenant_id = :tenant_id"]
    
    Gate4 --> Gate5["Gate 5: Query Limit Enforcement\n• Inspects exp.Limit node\n• Injects LIMIT 100 if missing; clamps existing limit to <= 100"]
    
    Gate5 --> ReadOnly["Read-Only Transaction Sandbox\n• SET statement_timeout = 3000ms\n• SET TRANSACTION READ ONLY\n• Executes query & rolls back transaction to preserve session write capabilities"]
    
    ReadOnly --> AuditLog["Audit Logger\nCommits user prompt, generated SQL, sanitized SQL, exec duration, and row count"]
    
    AuditLog --> TabularOutput["Return Columns, Serialized Rows, and Execution Time"]
```

### The 5 Security Gates Explained

1. **Gate 1: Markdown Cleaning**: Normalizes LLM output and strips codeblock wrappers.
2. **Gate 2: AST Parsing & Mutation Rejection**: Uses `sqlglot` to parse the query into an Abstract Syntax Tree. Only single-statement queries with a root `exp.Select` node are permitted. Any destructive DDL/DML statement (`DROP`, `ALTER`, `TRUNCATE`, `INSERT`, `UPDATE`, `DELETE`) is immediately rejected.
3. **Gate 3: Schema Whitelist & Prohibited Functions**: Restricts accessible tables strictly to the 6 operational business tables. System administration and lateral movement functions (`pg_sleep`, `pg_read_file`, `version`, `current_user`, etc.) are blocked.
4. **Gate 4: Multi-Tenant AST Injection**: Programmatically traverses the AST and injects `{alias}.tenant_id = '{user_tenant_id}'` into the `WHERE` clause for every referenced table, preventing cross-tenant data leakage.
5. **Gate 5: Query Limit Enforcement**: Prevents denial-of-service through unbounded queries by injecting or capping `LIMIT 100`.

**Execution Sandbox**: Queries execute under `SET TRANSACTION READ ONLY` with a strict `SET statement_timeout = 3000` (3 seconds), followed by an automatic rollback to keep the database session write-capable for audit logging.

---

## 7. Evaluation

The platform includes an automated evaluation harness in `scripts/run_evaluation.py` and `src/services/evaluation.py` that benchmarks quality across three distinct pillars:

```mermaid
flowchart LR
    EvalHarness["Evaluation Suite\n(scripts/run_evaluation.py)"]
    
    EvalHarness --> Pillar1["Pillar 1: Deterministic Retrieval (L1)\n• Hit Rate@1, @3, @5\n• Mean Reciprocal Rank (MRR)"]
    EvalHarness --> Pillar2["Pillar 2: Model-as-a-Judge (L2)\n• Claim-Level Faithfulness Score (0.0 - 1.0)\n• Answer Relevance Score (0.0 - 1.0)\n• Detection of Unsupported Claims"]
    EvalHarness --> Pillar3["Pillar 3: Text-to-SQL Validation (L3)\n• AST Syntax Validity\n• Whitelist Compliance\n• Target Table Coverage vs. Golden Cases"]
```

### Running the Evaluation Suite
```bash
python scripts/run_evaluation.py
```

### Metrics & Quality Gates
- **Retrieval Quality**: Hit Rate@3 $\ge 0.70$, MRR $\ge 0.65$.
- **Faithfulness & Groundedness**: Average faithfulness score $\ge 0.75$, with strict penalty deductions for claims not directly substantiated by retrieved context passages.
- **SQL Integrity**: 100% AST pass rate, zero unauthorized table references, and correct foreign key join synthesis.
- **Routing Accuracy**: Intent classification benchmarked against golden test prompts.

---

## 8. Setup

### 8.1 Prerequisites
- **Python 3.12+**
- **Node.js 20+ & npm**
- **PostgreSQL 16** with the `pgvector` extension installed
- **Google Gemini API Key**

### 8.2 Environment Configuration
Create a `.env` file in the project root:

```env
# Application Settings
PROJECT_NAME="Enterprise RAG & Operations Intelligence"
ENVIRONMENT="development"
DEBUG=true

# Database Connection (Automatic postgresql+asyncpg adapter)
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_rag"

# Google Gemini Configuration
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

### 8.3 Local Development Setup

```bash
# 1. Clone repository and set up Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install backend dependencies in editable mode
pip install -e .

# 3. Seed operational database entities and default admin
python scripts/seed_operational_data.py

# 4. Start FastAPI development server
uvicorn src.main:app --reload --port 8000
```

In a separate terminal, start the Next.js frontend:

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Launch development server with Turbopack
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

#### Default Demo Credentials
- **Email**: `admin@gmail.com`
- **Password**: `Admin@12345`
- **Role**: `ADMIN`
- **Tenant ID**: `default_tenant`

---

### 8.4 Production Deployment

#### Option A: Docker Compose (Local / Self-Hosted)
Run the full production stack with PostgreSQL, pgvector, the FastAPI backend, and the Next.js frontend:

```bash
docker compose up -d --build
```

#### Option B: Render Blueprint (100% Free Tier Cloud Deployment)
The repository includes an infrastructure-as-code [`render.yaml`](./render.yaml) blueprint that deploys:
1. **Managed PostgreSQL Database** (Free Tier with vector extension)
2. **FastAPI Web Service** (Built from [`Dockerfile`](./Dockerfile) with embedded background worker and `AUTO_SEED=true`)
3. **Next.js Web Service** (Built from `./frontend` on Node runtime)

To deploy:
1. Push this repository to GitHub.
2. In the Render Dashboard, select **New > Blueprint**.
3. Connect your repository. Render automatically configures the database and web services.
4. Input your `GEMINI_API_KEY` under the backend environment variables.
5. Access your live application and sign in with the default administrator credentials.

---

## 9. Screenshots / Demo

The frontend is organized into 5 purpose-built studios accessible from the top navigation bar:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  ENTERPRISE INTELLIGENCE CONSOLE        [Unified Chat] [RAG] [SQL] [Ingestion] [Tracer] │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 9.1 The Five Studio Views

1. **Unified Chat Console**:
   - Natural language interface that automatically classifies queries, displays execution route badges (`RAG`, `SQL`, `HYBRID_AGENT`), and provides execution time metrics, citation chips, and formatted tabular outputs.

2. **Policy RAG Studio**:
   - Dedicated document question-answering console featuring real-time Server-Sent Events (SSE) token streaming. Bracket citations (`[1]`, `[2]`) open an interactive citation drawer showing source files, page numbers, and exact passage snippets.

3. **Text-to-SQL Studio**:
   - Natural language database console with interactive query generation, raw SQL preview, operational schema explorer, tabular result sets, and real-time security audit log inspection.

4. **Document Ingestion Hub**:
   - Drag-and-drop document upload interface supporting PDF, DOCX, TXT, and Markdown files. Allows configuring RBAC access roles (`ADMIN`, `MANAGER`, `ANALYST`) and displays document lifecycle status (`PENDING` $\rightarrow$ `PROCESSING` $\rightarrow$ `ACTIVE`) with real-time chunk inspectors.

5. **Agent Tracer**:
   - Visual execution graph inspector for multi-step agent workflows. Displays sub-query decomposition, parallel task execution status, execution durations, and final executive synthesis.

---

### 9.2 Practical Demo Scenarios

#### Scenario A: Unstructured Policy Retrieval (RAG Route)
- **User Prompt**: *"What are the meal allowance limits and lodging rules for domestic travel?"*
- **Router Classification**: `RAG` (~0ms heuristic match on policy keywords).
- **Execution**: Hybrid search (dense pgvector + sparse TSVECTOR) merged with RRF and re-ranked via FlashRank.
- **Output**: Grounded answer with interactive citations:
  > *"According to the Company Travel Policy, the maximum domestic daily meal allowance is $75 per day [1]. Lodging expenses must not exceed $200 per night for standard business travel [2]."*

#### Scenario B: Operational Database Query (SQL Route)
- **User Prompt**: *"What is the annual budget of the Engineering department and how many active employees work there?"*
- **Router Classification**: `SQL` (~0ms heuristic match on budget/aggregation keywords).
- **Generated & Sanitized SQL**:
  ```sql
  SELECT d.name, d.annual_budget, COUNT(e.id) AS active_employee_count
  FROM departments AS d
  JOIN employees AS e ON e.department_id = d.id
  WHERE d.code = 'ENG' AND e.employment_status = 'ACTIVE' AND d.tenant_id = 'default_tenant' AND e.tenant_id = 'default_tenant'
  GROUP BY d.name, d.annual_budget
  LIMIT 100;
  ```
- **Output**: Formatted interactive data table + natural language explanation summary.

#### Scenario C: Multi-Step Compliance Audit (HYBRID_AGENT Route)
- **User Prompt**: *"Compare our travel policy meal allowance limits with actual meal expenses in the Engineering department to identify any non-compliant claims."*
- **Router Classification**: `HYBRID_AGENT` (cross-referencing intent detected).
- **Orchestration Execution**:
  1. Planner decomposes inquiry into:
     - `document_question`: *"What is the daily meal allowance limit in the company travel policy?"*
     - `database_question`: *"List all operational expenses in the Meals category for the Engineering department."*
  2. Concurrent execution (`asyncio.gather`) runs document retrieval and sandboxed SQL query in parallel.
  3. Synthesizer cross-references policy limit ($75/day) against database expense rows.
- **Output**: Executive briefing highlighting compliant and non-compliant expense claims, with direct citations to the policy document and underlying relational expense rows.
