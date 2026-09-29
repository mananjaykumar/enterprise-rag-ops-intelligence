# Phase 10: Free Cloud Deployment & CI/CD
## Engineering Specification & Implementation Guide

**Phase:** 10  
**Status:** Completed ✅  
**Prerequisites:** Phases 01 through 09  
**Objective:** Package the entire enterprise platform into a hardened, non-root multi-stage Docker container optimized for free-tier cloud environments (< 512MB RAM budget), establish automated GitHub Actions CI/CD quality gates, and document a zero-cost cloud deployment strategy across Neon/Supabase and Render/Fly.io.

---

## 1. Architectural Philosophy & Zero-Cost Strategy

Enterprise AI systems often incur massive cloud hosting bills due to heavy in-memory models and dedicated infrastructure. Our platform is engineered from the ground up for **Zero-Cost Enterprise Viability**:

```
                       ZERO-COST CLOUD ARCHITECTURE
  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │   [Client / Browser / API Consumer]                             │
  │                   │                                              │
  │                   ▼ HTTPS                                        │
  │   ┌──────────────────────────────────────────────────────────┐   │
  │   │ Container Web Service (Render / Koyeb / Fly.io Free Tier)│   │
  │   │ - Multi-stage Python 3.12-slim runtime (< 220MB RAM)     │   │
  │   │ - Non-root execution (`appuser` UID 10001)               │   │
  │   │ - Dynamic port binding (${PORT:-8000})                   │   │
  │   │ - FlashRank ONNX Quantized Reranker (~40MB RAM)          │   │
  │   └───────────────┬──────────────────────────┬───────────────┘   │
  │                   │                          │                   │
  │                   ▼                          ▼                   │
  │   ┌───────────────────────────┐  ┌───────────────────────────┐   │
  │   │ Cloud Database (Neon/Supa)│  │ Telemetry (Langfuse Cloud)│   │
  │   │ - PostgreSQL 16 + pgvector│  │ - Free Developer Tier     │   │
  │   │ - ACID multi-tenant tables│  │ - 50,000 traces / month   │   │
  │   │ - HNSW index acceleration │  │ - Token & latency audit   │   │
  │   └───────────────────────────┘  └───────────────────────────┘   │
  │                   │                                              │
  │                   ▼ HTTPS                                        │
  │   ┌──────────────────────────────────────────────────────────┐   │
  │   │ Cloud AI Services (Google Gemini Free Tier)             │   │
  │   │ - gemini-3.5-flash-lite (15 RPM free tier)              │   │
  │   │ - text-embedding-004 (768-dimensional embeddings)        │   │
  │   └──────────────────────────────────────────────────────────┘   │
  │                                                                  │
  │   TOTAL MONTHLY OPERATING EXPENSE: $0.00 / month                 │
  └──────────────────────────────────────────────────────────────────┘
```

---

## 2. Infrastructure Budget & Memory Allocation

Free-tier cloud providers enforce a strict **512MB RAM cap**. Applications that exceed this limit are killed immediately by Linux Out-Of-Memory (OOM) handlers.

### Memory Breakdown:
| Component | Implementation Choice | RAM Footprint | Rationale |
|---|---|---|---|
| **API Framework** | FastAPI + Uvicorn + AsyncIO | ~65 MB | Lightweight asynchronous event loop. |
| **Database Driver** | Asyncpg + SQLAlchemy 2.0 | ~25 MB | Native C-level asynchronous connection pool. |
| **Vector Reranker** | FlashRank (`ms-marco-TinyBERT`) | ~40 MB | ONNX quantized CPU runtime. Avoids PyTorch (~1.2GB). |
| **Agent Machine** | LangGraph StateGraph | ~15 MB | Pure Python state transitions without bloat. |
| **Tracing SDK** | Langfuse SDK v4 (Async Buffer) | ~20 MB | Background batch queue with minimal memory usage. |
| **Runtime Overhead** | Python 3.12-slim OS base | ~45 MB | Minimal Debian packages. |
| **Total Memory** | **Production Working Set** | **~210 MB** | **Safe buffer: 302 MB under 512 MB ceiling.** |

---

## 3. Production Multi-Stage Containerization

The production `Dockerfile` uses a two-stage build to isolate build tools from the final runtime container:

1. **Stage 1 (`builder`)**: Installs `gcc`, `build-essential`, and `libpq-dev` to compile C-extensions (`asyncpg`, `bcrypt`, `pgvector`). Installs all dependencies into `/install`.
2. **Stage 2 (`runtime`)**: Minimal `python:3.12-slim` image containing only shared C runtime libraries (`libpq5`).
3. **Security (`appuser`)**: Drops root privileges by creating an unprivileged user (`appuser`, UID `10001`).
4. **Cloud Port Binding**: Reads the dynamic `$PORT` environment variable injected by hosting providers, defaulting to `8000`.
5. **Zero-Dependency Healthcheck**: Uses standard library `urllib.request` to poll `/health` every 30 seconds without installing `curl`.

---

## 4. Automated CI/CD Pipeline (`.github/workflows/ci.yml`)

The repository enforces **Five Automated Quality Gates** on every push and pull request to `main`:

* **Gate 1A & 1B: Code Quality & Formatting**: Ruff checks all code against PEP 8, import sorting, and formatting standards.
* **Gate 2: Database Service Container**: Automatically spins up `pgvector/pgvector:pg16` in GitHub Actions to test real database interactions.
* **Gate 3: Full Unit Test Suite**: Executes 26 unit tests covering Authentication, Documents, Hybrid Retrieval, Grounded RAG, Text-to-SQL, Agent Orchestration, and Observability.
* **Gate 4: Evaluation Benchmark Gate**: Runs `scripts/run_evaluation.py` against the golden dataset. Fails the build if:
  - Retrieval Hit Rate@3 < 70%
  - Answer Faithfulness < 75%
  - Answer Relevance < 75%
  - SQL AST Pass Rate != 100%
  - Intent Routing Accuracy < 80%
* **Gate 5: Production Docker Build Gate**: Builds the multi-stage image to guarantee clean compilation without layer errors.

---

## 5. Step-by-Step Cloud Deployment Walkthrough

### Step 1: Provision Free Cloud Database (Neon / Supabase)
1. Sign up for a free account at [Neon.tech](https://neon.tech) or [Supabase.com](https://supabase.com).
2. Create a new PostgreSQL 16 project.
3. In the SQL Editor, verify that the `pgvector` extension is active:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. Copy your asynchronous connection string (for example: `postgresql+asyncpg://user:password@ep-xyz.neon.tech/neondb?ssl=require`).

### Step 2: Deploy Web Service to Render / Koyeb / Fly.io
1. Push your repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com), click **New +** -> **Web Service**.
3. Connect your GitHub repository.
4. Select **Docker** as the runtime environment.
5. Set the instance type to **Free (512 MB RAM / 0.1 CPU)**.
6. Configure the following Environment Variables:
   - `DATABASE_URL`: Your Neon/Supabase connection string.
   - `GEMINI_API_KEY`: Your Google Gemini API Key.
   - `JWT_SECRET_KEY`: A secure 32+ character random string.
   - `ENVIRONMENT`: `production`
   - `LANGFUSE_PUBLIC_KEY`: Your Langfuse Cloud public key.
   - `LANGFUSE_SECRET_KEY`: Your Langfuse Cloud secret key.
   - `LANGFUSE_HOST`: `https://cloud.langfuse.com`
   - `LANGFUSE_ENABLED`: `true`
7. Click **Deploy**. The platform will build the multi-stage image and run health checks automatically.

---

## 6. Senior Systems Architect Interview Defense

### Q1: How do you guarantee your Python container will not crash with Out-Of-Memory errors on free cloud tiers with only 512MB RAM?
> *"Most generative AI applications crash on free tiers because they load full PyTorch binaries (~1.2GB) or heavy Hugging Face transformers into memory. We prevented this with two architectural choices: first, we offload embedding generation and LLM inference to Google Gemini APIs, keeping our process stateless. Second, for local reranking, we chose FlashRank—a quantized ONNX runtime with a TinyBERT model that operates in under 40MB RAM. The total resident memory of our FastAPI service with asyncpg, SQLAlchemy, and LangGraph is approximately 210MB, leaving over 300MB of safe headroom under the 512MB ceiling."*

### Q2: Why run your container as an unprivileged user (`appuser` UID 10001) instead of the default `root` user?
> *"Running containers as root violates the Principle of Least Privilege. In the event of a remote code execution vulnerability or a container breakout flaw in the Linux kernel, a root process inside the container can potentially gain root access to the underlying host. By switching to `appuser` (UID 10001) with read-only permissions on everything except designated working directories, any exploit is contained within an unprivileged sandbox."*

### Q3: How does your deployment handle cold-starts when free-tier services spin down after inactivity?
> *"Free containers on platforms like Render spin down after 15 minutes of inactivity. When a request arrives, startup latency depends heavily on container size. By using a multi-stage Docker build with `python:3.12-slim` and removing compilers and package caches, our container image remains under 250MB compressed. Our startup routine performs lazy loading for the FlashRank reranker and runs a zero-dependency health check endpoint (`/health`) that validates database connectivity in milliseconds without calling LLMs, allowing the container to become healthy within 3 to 5 seconds."*

### Q4: Why include an evaluation harness (`scripts/run_evaluation.py`) directly inside your CI/CD pipeline?
> *"Traditional CI/CD pipelines only check whether code builds and passes unit tests. However, in an AI application, code can be 100% syntactically correct while retrieval quality or prompt groundedness degrades significantly. By making our golden benchmark dataset and evaluation harness Gate 4 in our GitHub Actions workflow, any change to chunking strategy, prompts, reranking weights, or SQL guardrails that drops Hit Rate below 70% or Answer Faithfulness below 75% immediately breaks the build and prevents deployment."*

### Q5: What is the architectural difference between storing vector embeddings in a standalone vector database versus Neon/Supabase with `pgvector` on free cloud tiers?
> *"Using a separate vector database (like Pinecone) introduces distributed state, potential network latency overhead, and dual-write consistency problems. With Neon or Supabase, our relational business data (expenses, employees, departments) and our unstructured document embeddings reside in the same PostgreSQL instance. This enables true Pre-Retrieval Filtering, where tenant boundaries and document permissions are enforced in the exact same SQL query that evaluates vector cosine similarity. Furthermore, it consolidates backup, replication, and disaster recovery into a single PostgreSQL engine for $0.00/month."*
