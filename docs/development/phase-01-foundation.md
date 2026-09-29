# Phase 01: Foundation & Contracts
## Engineering Specification & Implementation Guide

**Phase:** 01  
**Status:** `COMPLETED` ✅  
**Objective:** Establish the production-grade application skeleton, containerized PostgreSQL with pgvector, strict environment validation, and core domain interfaces (Ports & Adapters).

---

## 1. Objective
Establish the foundational infrastructure and code contracts for the Enterprise Knowledge & Operations Intelligence Platform. At the end of this phase, the developer will have a running local PostgreSQL 16 container with `pgvector` enabled, a validated configuration system via `pydantic-settings`, core abstract interfaces for AI/Storage/Queue providers, and a running FastAPI application with active database health verification.

---

## 2. Why This Phase Exists
A common failure in AI engineering projects is rushing into prompt engineering or chunking scripts before establishing architectural boundaries. 
* Without **abstract provider interfaces**, application logic becomes tightly coupled to a single vendor (e.g., hardcoded Gemini/OpenAI calls scattered across routers).
* Without **strict configuration validation**, missing environment variables or invalid credentials fail silently at runtime during user requests rather than failing fast at application boot.
* Without a **reproducible local containerized database**, development environment discrepancies lead to "works on my machine" bugs.

---

## 3. Architecture & Directory Structure

We use a **Modular Monolith** pattern adhering to **Hexagonal Architecture (Ports & Adapters)**.

```text
enterprise-rag-intelligence/
├── docker-compose.yml              # Local PostgreSQL 16 + pgvector container
├── .env.example                    # Template for environment configuration
├── requirements.txt                # Pinned production dependencies
├── pyproject.toml                  # Project packaging & tool settings (ruff, mypy)
├── docs/                           # Architecture, design & phase documentation
│   ├── architecture/
│   │   └── system-architecture.md
│   └── development/
│       └── phase-01-foundation.md
├── src/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application factory & lifespan
│   ├── core/                       # Cross-cutting concerns
│   │   ├── __init__.py
│   │   ├── config.py               # Pydantic Settings & environment validation
│   │   ├── logging.py              # Structured JSON logging
│   │   └── exceptions.py           # Core domain exceptions
│   ├── db/                         # Database engine & session management
│   │   ├── __init__.py
│   │   ├── session.py              # SQLAlchemy async engine & session factory
│   │   └── base.py                 # Declarative base & common model mixins
│   ├── domain/                     # Pure domain layer (no external framework imports)
│   │   ├── __init__.py
│   │   └── interfaces/             # Abstract Base Classes (Ports)
│   │       ├── __init__.py
│   │       ├── llm.py              # BaseLLMClient interface
│   │       ├── embedding.py        # BaseEmbeddingClient interface
│   │       ├── storage.py          # BaseStorageClient interface
│   │       └── queue.py            # BaseJobQueueClient interface
│   └── api/                        # HTTP transport layer (FastAPI routers)
│       ├── __init__.py
│       ├── dependencies.py         # FastAPI dependency injection providers
│       └── v1/
│           ├── __init__.py
│           └── health.py           # Health & readiness probe endpoints
└── tests/
    ├── __init__.py
    ├── conftest.py                 # Pytest fixtures & test database setup
    └── unit/
        ├── test_config.py
        └── test_health.py
```

---

## 4. Key Contracts & Abstract Interfaces

### 4.1 `BaseLLMClient` (`src/domain/interfaces/llm.py`)
```python
from abc import ABC, abstractmethod
from typing import Any, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMClient(ABC):
    @abstractmethod
    async def generate_text(
        self, prompt: str, system_instruction: str | None = None, **kwargs
    ) -> str:
        """Generate unstructured text completion."""
        pass

    @abstractmethod
    async def generate_structured(
        self, prompt: str, response_schema: type[T], system_instruction: str | None = None, **kwargs
    ) -> T:
        """Generate strictly typed structured output adhering to a Pydantic schema."""
        pass
```

### 4.2 `BaseEmbeddingClient` (`src/domain/interfaces/embedding.py`)
```python
from abc import ABC, abstractmethod


class BaseEmbeddingClient(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the active embedding model (e.g., 'gemini-embedding-001')."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality (e.g., 768)."""
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Generate embedding vector for a search query."""
        pass

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of document chunks."""
        pass
```

### 4.3 `BaseStorageClient` (`src/domain/interfaces/storage.py`)
```python
from abc import ABC, abstractmethod
from typing import BinaryIO


class BaseStorageClient(ABC):
    @abstractmethod
    async def save_file(self, file_path: str, data: BinaryIO | bytes) -> str:
        """Persist file to storage and return its URI."""
        pass

    @abstractmethod
    async def read_file(self, file_path: str) -> bytes:
        """Retrieve raw file bytes from storage."""
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Remove file from storage."""
        pass
```

---

## 5. Implementation Plan

1. **Step 1: Dependency Management (`requirements.txt` / `pyproject.toml`)**
   * Dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `pgvector`, `alembic`, `httpx`, `pytest`, `pytest-asyncio`.
2. **Step 2: Local Database Infrastructure (`docker-compose.yml`)**
   * Service `postgres`: Image `pgvector/pgvector:pg16`, exposed on port `5432`, volume mounted to `pgdata`, healthcheck enabled.
3. **Step 3: Configuration Management (`src/core/config.py`)**
   * Define `Settings` using `pydantic-settings.BaseSettings`.
   * Environment variables: `PROJECT_NAME`, `ENVIRONMENT`, `DATABASE_URL`, `GEMINI_API_KEY`, `ACTIVE_EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`.
4. **Step 4: Database Engine & Session Factory (`src/db/session.py`)**
   * Initialize async SQLAlchemy engine with connection pooling settings suitable for low-memory tiers (`pool_size=5`, `max_overflow=10`).
   * Provide an async session generator for FastAPI dependency injection.
5. **Step 5: Abstract Interface Definitions (`src/domain/interfaces/`)**
   * Define `llm.py`, `embedding.py`, `storage.py`, `queue.py`.
6. **Step 6: FastAPI Application Factory & Health Check (`src/main.py` & `src/api/v1/health.py`)**
   * Create `GET /api/v1/health` returning application status, version, and database connectivity check (`SELECT 1`).
7. **Step 7: Verification Tests (`tests/unit/test_health.py`)**
   * Verify test suite executes via `pytest`.

---

## 6. Failure Modes & Edge Cases
* **Database Unavailable at Boot:** Use FastAPI lifespan context manager to ping the database during startup. Log a structured error and fail immediately if PostgreSQL is unreachable.
* **Missing Secret / API Key:** Pydantic `BaseSettings` will raise a ValidationError on startup if required configuration (e.g., `GEMINI_API_KEY`) is missing, preventing silent partial boots.
* **Port Conflicts:** Ensure `docker-compose.yml` maps port `5432` cleanly or allows port override via `.env` if local PostgreSQL is already running on the host.

---

## 7. Completion Criteria
* [x] `docker compose up -d` boots PostgreSQL 16 with `pgvector` extension installed.
* [x] Application configuration loads and validates against `.env`.
* [x] Abstract interface classes in `src/domain/interfaces/` are defined without syntax or import errors.
* [x] `GET /api/v1/health` returns `{"status": "healthy", "database": "connected"}`.
* [x] Unit test suite (`pytest -v`) executes and passes successfully.

---

## 8. Phase 01 Engineering Log: Decisions, Doubts & Deep Dives

### 8.1 Dependency Management: `pyproject.toml` vs. `requirements.txt`
* **Doubt / Question:** If we are using `pyproject.toml`, why do we need `requirements.txt`?
* **Technical Explanation:**
  * `pyproject.toml` (PEP 517/518/621) defines **abstract requirements** (what the package needs to run, broad semantic version ranges) along with build tool and linter configs (`ruff`, `mypy`, `pytest`).
  * `requirements.txt` defines **concrete lock snapshots** (exact pinned versions of every transitive dependency and hash).
  * In modern Python engineering, maintaining both manually creates configuration drift.
* **Decision:** `pyproject.toml` is locked as our **Single Source of Truth**. We install in editable mode (`pip install -e ".[dev]"`). If our free-tier PaaS deployment in Phase 10 demands a `requirements.txt`, we will generate it deterministically via `uv pip compile pyproject.toml -o requirements.txt` rather than maintaining duplicate lists.

### 8.2 WSL 2 & Development Environment Gotchas
* **Hidden Virtual Environment:** `python3 -m venv .venv` creates a hidden directory in Linux. Typing `source <venv>/bin/activate` fails because `<venv>` is interpreted as shell input redirection. The correct invocation is `source .venv/bin/activate`.
* **WSL 2 Docker Integration:** Running `docker compose` inside WSL 2 requires the Docker Desktop WSL 2 integration bridge to be enabled under Docker Desktop $\rightarrow$ Settings $\rightarrow$ Resources $\rightarrow$ WSL Integration.
* **Vector Extension Activation:** The `pgvector/pgvector:pg16` Docker image has the binary compiled, but PostgreSQL requires running `CREATE EXTENSION IF NOT EXISTS vector;` in the target database before vector operations can be used.

### 8.3 The Redis Debate: The Dual-Write Problem & 512MB RAM Budget
* **Doubt / Question:** Why did we omit Redis for our background jobs? How do modern large-scale applications use both PostgreSQL and Redis without bottlenecks or atomic transaction inconsistencies?
* **Architectural Deep Dive:**
  1. **The 512 MB Free-Tier Cloud Constraint:** Free PaaS tiers (Render, Fly.io, Koyeb) cap containers at 512 MB of RAM. Running FastAPI (~120MB) + PostgreSQL (~150MB) + Redis (~60MB) + Celery worker (~150MB) pushes memory consumption near 500 MB, risking catastrophic Out-Of-Memory (OOM) kills.
  2. **The Dual-Write Problem:** When an application attempts to write to two independent systems (PostgreSQL for data, Redis for queuing), network timeouts or partial crashes lead to state divergence:
     - Document saved in PostgreSQL, but Redis enqueue fails $\rightarrow$ "Ghost Document" that is never processed.
     - Redis enqueue succeeds, but PostgreSQL transaction rolls back $\rightarrow$ Worker attempts to process a non-existent document ID.
  3. **How High-Scale Tech Companies Solve This:**
     - **Transactional Outbox Pattern:** The API writes the document and an outbox event to PostgreSQL inside a single ACID transaction. A background relay (reading an outbox table or listening to Postgres WAL via Debezium) pushes events to Redis/Kafka. *PostgreSQL is effectively used as the initial queue!*
     - **Postgres `SKIP LOCKED`:** Modern PostgreSQL supports `SELECT ... FOR UPDATE SKIP LOCKED`, which allows multiple concurrent workers to dequeue jobs without table locking or race conditions.
  4. **The Decision:** Start with a PostgreSQL-native queue (`ingestion_jobs` table). It provides ACID guarantees with zero extra containers. By placing the queue behind `BaseJobQueueClient`, we preserve the ability to migrate to Redis/Celery or AWS SQS seamlessly without modifying business logic.

---

## 9. Interview Defense Questions & Explanations (Phase 01)

### Q1: Why did you choose `pyproject.toml` over `requirements.txt`?
> *"We follow modern PEP 621 standards where `pyproject.toml` acts as the single source of truth for project metadata, abstract dependencies, and tooling configuration (Ruff, Mypy, Pytest). Maintaining both manually causes version drift. For deployment determinism, we rely on lockfiles generated via `uv` or pip-tools rather than hand-crafted requirements files."*

### Q2: Why not run Redis alongside PostgreSQL from Day 1 for background tasks?
> *"Introducing Redis prematurely introduces two architectural liabilities: first, it violates our 512MB RAM ceiling on free cloud tiers. Second, naive dual-writes between PostgreSQL and Redis create the Dual-Write Problem, where failure in one system leaves ghost records in the other. By using PostgreSQL's native `FOR UPDATE SKIP LOCKED`, we achieve true ACID atomicity: the document metadata and ingestion job are committed in the exact same database transaction. Because we decoupled the queue behind a `BaseJobQueueClient` interface, we can layer in Redis using the Transactional Outbox Pattern whenever throughput demands it."*

### Q3: How do modern architectures eliminate the Dual-Write problem when using both Postgres and Redis?
> *"High-scale architectures use the Transactional Outbox Pattern or Change Data Capture (CDC) via PostgreSQL's Write-Ahead Log (WAL) with tools like Debezium. The application writes solely to the ACID-compliant relational store. A secondary relay process or replication stream reads the committed log and asynchronously dispatches tasks to Redis or Kafka, ensuring at-least-once delivery without distributed two-phase commits."*

