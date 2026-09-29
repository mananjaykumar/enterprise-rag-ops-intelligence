# Phase 02: Authentication, RBAC & Multi-Tenancy
## Engineering Specification & Implementation Guide

**Phase:** 02  
**Status:** `COMPLETED` ✅  
**Prerequisites:** Phase 01: Foundation & Contracts (Completed)  
**Objective:** Implement JWT authentication, Role-Based Access Control (RBAC: `admin`, `manager`, `analyst`), and request-scoped Tenant Context propagation to support Pre-Retrieval filtering.

---

## 1. Objective
Establish the enterprise security perimeter. At the end of Phase 02, the platform will support secure user registration and login, password hashing via bcrypt, signed JSON Web Tokens (JWT), role-based endpoint protection (`require_roles`), and an authenticated `UserContext` that automatically propagates `tenant_id` and `user_roles` into upcoming RAG and Text-to-SQL operations.

---

## 2. Why This Phase Exists
A fatal flaw in many RAG architectures is implementing document ingestion and search *before* authentication, treating security as an afterthought. 
* In our locked architecture (**ADR-006**), security is enforced via **Hard Pre-Retrieval Filtering**:
  ```sql
  WHERE tenant_id = :user_tenant_id AND allowed_roles && :user_roles
  ```
* If we do not establish the `UserContext` (identity, tenant, and roles) now, every retrieval and SQL service built in subsequent phases would have to be refactored later to accept security parameters.

---

## 3. Architecture & Security Flow

```text
HTTP Request (Header: Authorization: Bearer <JWT>)
                      ↓
+-------------------------------------------------------------+
| FASTAPI AUTH DEPENDENCY (get_current_user)                  |
|                                                             |
|  1. Extract Bearer token from HTTP Authorization header     |
|  2. Decode & verify JWT signature using SECRET_KEY (HS256)  |
|  3. Validate token expiration (exp claim)                   |
|  4. Extract subject (user_id), tenant_id, and role claims   |
|  5. Fetch active user from database (or build UserContext)  |
+-------------------------------------------------------------+
                      ↓
+-------------------------------------------------------------+
| RBAC ENFORCER (require_roles(["admin", "manager"]))         |
|                                                             |
|  - Verifies user.role in allowed_roles                      |
|  - Raises HTTP 403 FORBIDDEN if unauthorized                |
+-------------------------------------------------------------+
                      ↓
Endpoint / Service Layer receives authenticated `UserContext`
```

---

## 4. Database Schema: Users

```sql
CREATE TYPE user_role AS ENUM ('admin', 'manager', 'analyst');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant',
    email VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    role user_role NOT NULL DEFAULT 'analyst',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_tenant_email UNIQUE (tenant_id, email)
);

CREATE INDEX idx_users_tenant_role ON users(tenant_id, role);
```

---

## 5. Directory & File Plan

```text
src/
├── core/
│   ├── config.py               # (Add JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES)
│   └── security.py             # Password hashing (bcrypt) & JWT token encoding/decoding
├── db/
│   ├── base.py                 # SQLAlchemy DeclarativeBase
│   └── models/
│       ├── __init__.py
│       └── user.py             # User SQLAlchemy ORM model
├── schemas/
│   ├── __init__.py
│   └── auth.py                 # Pydantic schemas (UserCreate, UserResponse, Token, LoginRequest)
└── api/
    └── v1/
        ├── auth.py             # Auth endpoints (/register, /login, /me, /admin-only)
        └── dependencies.py     # Auth dependencies (get_current_user, require_roles)
tests/
└── unit/
    └── test_auth_api.py        # Registration, login & RBAC endpoint tests
```

---

## 6. Implementation Plan

1. **Step 1: Core Security Utilities (`src/core/security.py`)**
   * Password hashing & verification using native `bcrypt`.
   * JWT creation and decoding using `pyjwt`.
2. **Step 2: User ORM Model (`src/db/models/user.py`)**
   * Define `User` model matching the schema with role enum and `tenant_id`.
3. **Step 3: Pydantic Validation Schemas (`src/schemas/auth.py`)**
   * Input: `UserRegisterRequest`, `LoginRequest`.
   * Output: `TokenResponse`, `UserResponse`.
4. **Step 4: FastAPI Security Dependencies (`src/api/v1/dependencies.py`)**
   * `get_current_user`: Extracts token, decodes claims, verifies user in DB.
   * `require_roles`: Role-based authorization decorator / dependency factory.
5. **Step 5: Authentication Router (`src/api/v1/auth.py`)**
   * `POST /api/v1/auth/register` (creates user with hashed password).
   * `POST /api/v1/auth/login` (verifies credentials, returns access token).
   * `GET /api/v1/auth/me` (returns current user profile and role).
   * `GET /api/v1/auth/admin-only` (demonstrator endpoint verifying 403 enforcement).
6. **Step 6: Automated Test Suite (`tests/unit/test_auth_api.py`)**
   * Test registration, successful login, incorrect password rejection, and RBAC 403 enforcement.

---

## 7. Completion Criteria
* [x] Database schema initialized and `users` table auto-created via `Base.metadata.create_all`.
* [x] Password hashing handles salts and verifications securely via native `bcrypt`.
* [x] `POST /api/v1/auth/register` and `POST /api/v1/auth/login` operate successfully with JWT token issuance.
* [x] `require_roles([UserRole.ADMIN])` returns HTTP 403 Forbidden when accessed by an `analyst`.
* [x] Unit test suite (`pytest -v`) passes with 100% green status on authentication and RBAC checks.

---

## 8. Phase 02 Engineering Log: Decisions, Doubts & Deep Dives

### 8.1 Modern Linting with Ruff: B008 & Annotated Dependencies
* **Linting Catch:** Flake8-bugbear flagged `B008: Do not perform function call Depends in argument defaults`.
* **Resolution:** Switched to modern FastAPI idiomatic syntax: `Annotated[AsyncSession, Depends(get_db)]`. This avoids evaluating function calls in default arguments and provides cleaner type inference without silencing linter warnings.
* **Enum Standards (UP042):** Replaced legacy `class UserRole(str, enum.Enum)` with Python 3.11+ native `class UserRole(enum.StrEnum)`.

### 8.2 Pytest-Asyncio & SQLAlchemy Connection Pool Event Loop Collision
* **Failure Encountered:** Running multiple async test files caused: `RuntimeError: Event loop is closed` and HTTP 503.
* **Root Cause:** By default, `pytest-asyncio` creates a new event loop for each test function. The global SQLAlchemy `engine` retained connection sockets bound to the closed previous event loop.
* **The Fix:** Added an `autouse=True` fixture in `tests/conftest.py` calling `await engine.dispose()`. This guarantees connections are gracefully terminated inside their own event loop before pytest tears it down.

---

## 9. Interview Defense Questions & Explanations (Phase 02)

### Q1: Why use `typing.Annotated` for FastAPI dependencies instead of default parameter assignments?
> *"Default arguments like `db: AsyncSession = Depends(get_db)` violate Python's best practice against calling functions in default argument signatures (flake8 rule B008). Using `Annotated[AsyncSession, Depends(get_db)]` separates the type annotation from the metadata injection, keeps default parameters empty, and is the modern standard for FastAPI 0.95+."*

### Q2: How did you design multi-tenancy in your user schema?
> *"We implemented a composite unique constraint on `(tenant_id, email)` rather than a global unique constraint on email. This allows the same email address to exist across different tenant boundaries without namespace collisions, while indexing `(tenant_id, role)` ensures fast, index-backed RBAC filtering."*

### Q3: Why does `asyncpg` raise `RuntimeError: Event loop is closed` in pytest, and how did you resolve it?
> *"In asynchronous test suites, each test runs in an isolated asyncio event loop. If an async connection pool is created globally, its connection objects remain bound to the loop where they were opened. When a subsequent test runs in a new loop, touching the pool triggers loop-closure errors. We resolved this by adding an autouse teardown fixture calling `await engine.dispose()`, ensuring all pooled connections are cleanly closed within their originating event loop."*

