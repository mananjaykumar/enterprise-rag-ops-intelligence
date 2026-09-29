# Enterprise Knowledge & Operations Intelligence Platform

An enterprise-grade, multi-tenant Generative AI platform engineered for grounded Retrieval-Augmented Generation (RAG), secure natural-language Text-to-SQL analytics, and stateful agentic orchestration across corporate policies and structured relational databases.

Built with **FastAPI**, **PostgreSQL 16 + pgvector**, **Google Gemini 3.5 Flash Lite**, **FlashRank**, **LangGraph**, and **Langfuse**, optimized for **$0.00/month** zero-cost cloud deployment on a **< 512MB RAM** footprint.

---

## Architecture Overview

```
                                  API CLIENT / USER
                                         │
                                         ▼ HTTPS
                         ┌────────────────────────────────┐
                         │   FastAPI Modular Monolith     │
                         │   (Auth, RBAC, Observability)  │
                         └───────────────┬────────────────┘
                                         │
                                         ▼
                         ┌────────────────────────────────┐
                         │    Intent Classifier Router    │
                         └───────┬──────────────┬─────────┘
                                 │              │
                 ┌───────────────┘              └────────────────┐
                 ▼                                               ▼
     ┌───────────────────────┐                       ┌───────────────────────┐
     │  Document Policy RAG  │                       │   Secure Text-to-SQL  │
     │  - Markdown AST Parser│                       │   - 5-Gate Validation │
     │  - Hybrid BM25/Vector │                       │   - sqlglot AST Guard │
     │  - RRF + FlashRank    │                       │   - Read-Only User    │
     │  - Grounded Citations │                       │   - Schema Selector   │
     └───────────┬───────────┘                       └───────────┬───────────┘
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         │
                                         ▼
                         ┌────────────────────────────────┐
                         │   LangGraph State Machine      │
                         │   Multi-Step Hybrid Reasoning  │
                         └───────────────┬────────────────┘
                                         │
                                         ▼
                         ┌────────────────────────────────┐
                         │   PostgreSQL 16 + pgvector     │
                         │   - ACID Tenant Isolation      │
                         │   - Pre-Retrieval RBAC Filter  │
                         │   - SKIP LOCKED Job Queue      │
                         └────────────────────────────────┘
```

---

## Key Enterprise Capabilities

### 1. Multi-Tenant RBAC & Context Isolation
- Strict role-based access control (`ADMIN`, `COMPLIANCE_OFFICER`, `DEPARTMENT_HEAD`, `EMPLOYEE`).
- Pre-retrieval security filtering: document permissions and tenant boundaries are evaluated directly inside the database query, eliminating recall truncation.

### 2. High-Performance Hybrid Retrieval
- **Two-Tier Search**: Combines PostgreSQL Full-Text Search (tsvector / BM25-equivalent) with pgvector cosine distance embeddings.
- **Reciprocal Rank Fusion (RRF)**: Merges sparse keyword and dense semantic results.
- **FlashRank Re-ranking**: Locally scores candidates using quantized ONNX TinyBERT (~40MB RAM) without heavy PyTorch dependencies.

### 3. Secure 5-Gate Text-to-SQL Sandbox
- **Gate 1**: Natural-language schema selector matching user query to authorized tables.
- **Gate 2**: AST syntactic and security validation using `sqlglot` (rejects non-`SELECT` statements, data modifications, schema drops, and multi-queries).
- **Gate 3**: Strict table whitelisting preventing access to unauthorized operational tables.
- **Gate 4**: Dynamic tenant boundary enforcement (`WHERE tenant_id = :tenant_id`) and maximum row limit caps (`LIMIT 100`).
- **Gate 5**: Execution on an unprivileged read-only PostgreSQL connection with a hard 3-second statement timeout.

### 4. Stateful Hybrid Agent Orchestrator (LangGraph)
- Cyclical multi-step reasoning machine connecting policy documents with operational financial records.
- Deterministic routing for single-intent queries (RAG or SQL) with low latency fallback, reserving stateful graph cycles for complex cross-system compliance audits.

### 5. Automated Benchmark Evaluation Harness
- Integrated golden dataset with automated scoring for:
  - **Retrieval Hit Rate@K** and **Mean Reciprocal Rank (MRR)**.
  - **LLM-as-a-Judge** Faithfulness and Relevance metrics via structured JSON validation.
  - **SQL AST Compliance** checking syntax correctness and table permissions.
- Hard quality gates integrated directly into continuous integration workflows.

### 6. Multi-Layer Observability (Langfuse v4 & OpenTelemetry)
- Distributed tracing across HTTP middleware, vector retrieval, SQL sandbox execution, and LangGraph nodes.
- Request correlation headers (`X-Trace-ID`, `X-Response-Time-Ms`).
- Resilient local fallback mode ensuring zero runtime overhead when credentials are unset.

### 7. Zero-Cost Cloud Deployment (< 512MB RAM)
- Multi-stage Docker build producing a **162MB** compressed image.
- Runs as an unprivileged user (`appuser` UID 10001) for host security.
- Fully compatible with free cloud hosting tiers (Neon / Supabase + Render / Fly.io / Koyeb).

---

## Quality & Benchmark Metrics

| Metric Category | Target Threshold | Achieved Benchmark Score | Decision |
|---|---|---|---|
| **Retrieval Hit Rate@3** | >= 70.0% | **100.0%** | PASSED ✅ |
| **Mean Reciprocal Rank (MRR)** | >= 0.70 | **1.0000** | PASSED ✅ |
| **Answer Faithfulness (Judge)** | >= 75.0% | **100.0%** | PASSED ✅ |
| **Answer Relevance (Judge)** | >= 75.0% | **100.0%** | PASSED ✅ |
| **SQL AST Security Pass Rate** | 100.0% | **100.0%** | PASSED ✅ |
| **Query Routing Accuracy** | >= 80.0% | **100.0%** | PASSED ✅ |
| **Overall Quality Gate** | All Passing | **100.0%** | **PASSED ✅** |

---

## Project Structure

```
enterprise-rag-intelligence/
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated GitHub Actions CI/CD Quality Gates
├── data/
│   ├── evaluation/
│   │   ├── golden_dataset.json  # Benchmark ground truth dataset
│   │   └── latest_eval_report.json
│   └── sample_docs/             # Corporate policies & sample documents
├── docs/
│   ├── architecture/
│   │   └── system-architecture.md  # Architectural blueprint & Interview Defense
│   └── development/
│       ├── phase-01-foundation.md
│       ├── phase-02-auth-rbac.md
│       ├── phase-03-document-pipeline.md
│       ├── phase-04-hybrid-retrieval.md
│       ├── phase-05-grounded-rag.md
│       ├── phase-06-text-to-sql.md
│       ├── phase-07-stateful-orchestrator.md
│       ├── phase-08-evaluation-harness.md
│       ├── phase-09-observability-langfuse.md
│       └── phase-10-cloud-deployment.md
├── frontend/                    # Next.js 16 Enterprise Intelligence Dashboard
│   ├── src/
│   │   ├── app/                 # App Router (layout.tsx, page.tsx, globals.css)
│   │   ├── components/          # Navbar, UnifiedChat, SqlStudio, AgentTracer, DocumentIngest
│   │   └── lib/api.ts           # Type-safe API client connecting to FastAPI (:8000)
│   └── package.json
├── scripts/
│   └── run_evaluation.py        # Benchmark evaluation CLI runner
├── src/
│   ├── api/
│   │   ├── middleware/          # Observability & tracing headers
│   │   └── routes/              # Auth, Documents, RAG, SQL, Agent, Health
│   ├── core/                    # App configuration, security & logging
│   ├── db/
│   │   ├── models/              # SQLAlchemy models (User, Document, Chunks, Operational)
│   │   └── session.py           # Database engine & async connection sessions
│   ├── infrastructure/
│   │   └── ai/                  # Gemini LLM adapter & embedding clients
│   ├── schemas/                 # Pydantic validation contracts
│   └── services/                # Business logic, retrieval, SQL, router, agent
├── tests/
│   └── unit/                    # 26 unit tests (100% green passing)
├── Dockerfile                   # Multi-stage production container (< 512MB RAM)
├── .dockerignore
├── docker-compose.yml           # Local PostgreSQL 16 + pgvector service
└── pyproject.toml               # Single source of truth dependencies & tooling
```

---

## Quickstart Guide

### Prerequisites
- Python 3.12+
- Docker & Docker Compose
- Google Gemini API Key

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/your-org/enterprise-rag-intelligence.git
cd enterprise-rag-intelligence

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env with your GEMINI_API_KEY and JWT_SECRET_KEY
```

### 3. Start PostgreSQL with pgvector
```bash
docker compose up -d postgres
```

### 4. Run the Backend API Server
```bash
uvicorn src.main:app --reload --port 8000
```
Visit the interactive API documentation at: `http://localhost:8000/docs`

### 5. Run the Next.js Enterprise Dashboard (Frontend)
```bash
cd frontend
npm install
npm run dev
```
Open your browser at: **`http://localhost:3000`**

---

## Testing & Quality Assurance

Run the comprehensive test suite:
```bash
pytest tests/unit/ -v
```

Run code formatting and lint checks:
```bash
ruff check .
ruff format --check .
```

Run the benchmark evaluation harness:
```bash
python scripts/run_evaluation.py
```

Build the production container:
```bash
docker build -t enterprise-rag-intelligence:latest .
```

---

## License
MIT License. Free for commercial and educational use.
