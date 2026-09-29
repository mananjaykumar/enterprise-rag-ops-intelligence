# Phase 06: Secure Text-to-SQL Sandbox
## Engineering Specification & Implementation Guide

**Phase:** 06  
**Status:** Completed ✅  
**Prerequisites:** Phase 01: Foundation | Phase 02: Auth & RBAC | Phase 03: Document Ingestion | Phase 04: Hybrid Retrieval | Phase 05: Grounded RAG  
**Objective:** Implement enterprise-grade Text-to-SQL execution engine with operational business schemas, Gemini SQL generation, a 5-Gate Defense-in-Depth AST security sandbox (via `sqlglot`), multi-tenant injection, read-only transaction isolation, and audit logging.

---

## 1. Objective & Architecture Overview

Enable business analysts and enterprise users to query structured relational operational data (departments, employees, vendors, contracts, invoices, expenses) using natural language, with mathematical guarantees against data exfiltration, destructive SQL injection, cross-tenant data leakage, and runaway database queries.

```text
User Natural Language Prompt + Verified User Context (tenant_id)
                           ↓
[ Gate 1: Minimal Schema Selection ]
  - Exposes only operational business table DDL & foreign key relationships in system prompt
                           ↓
[ Gemini LLM (gemini-3.5-flash-lite) ]
  - Generates candidate PostgreSQL SELECT query
                           ↓
[ Gate 2: AST Parsing & Single Statement Verification (sqlglot) ]
  - Validates PostgreSQL dialect grammar
  - Rejects non-SELECT root AST (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.)
  - Rejects semicolon statement chaining / multi-statement queries
                           ↓
[ Gate 3: Table Whitelist & Function Sandbox ]
  - Allowed: departments, employees, vendors, contracts, invoices, operational_expenses
  - Blocked: users, documents, document_chunks, ingestion_jobs, pg_catalog, information_schema
  - Forbidden Functions: pg_sleep, pg_read_file, version, current_user, current_database, etc.
                           ↓
[ Gate 4: Multi-Tenant Injection & Read-Only Transaction ]
  - Injects AST WHERE alias.tenant_id = :tenant_id on all referenced tables
  - Executes within SET TRANSACTION READ ONLY isolation
                           ↓
[ Gate 5: Execution Guardrails & Timeouts ]
  - AST limit capping (injects or caps LIMIT <= 100)
  - Enforces statement timeout (SET statement_timeout = 3000ms)
                           ↓
[ Execution & Immutable Audit Logging ]
  - Records execution time, SQL query, user_id, tenant_id, row count in sql_query_audit_logs
                           ↓
[ Natural Language Result Synthesis ]
  - Gemini explains tabular query results in concise, executive-friendly summaries
```

---

## 2. Structured Operational Schemas

The following operational business tables have been established in PostgreSQL 16 with UUID primary keys and mandatory `tenant_id` columns:

1. **`departments`**: `id`, `tenant_id`, `code`, `name`, `annual_budget`, `created_at`
2. **`employees`**: `id`, `department_id`, `tenant_id`, `employee_code`, `full_name`, `email`, `role_title`, `employment_status`, `hire_date`
3. **`vendors`**: `id`, `tenant_id`, `vendor_code`, `name`, `category`, `risk_rating`, `is_active`
4. **`contracts`**: `id`, `vendor_id`, `associated_document_id`, `tenant_id`, `contract_number`, `title`, `total_value`, `start_date`, `end_date`, `auto_renew`, `status`
5. **`invoices`**: `id`, `vendor_id`, `contract_id`, `tenant_id`, `invoice_number`, `amount`, `issue_date`, `due_date`, `payment_status`, `paid_at`
6. **`operational_expenses`**: `id`, `department_id`, `employee_id`, `tenant_id`, `category`, `amount`, `currency`, `expense_date`, `description`, `approved`
7. **`sql_query_audit_logs`**: `id`, `tenant_id`, `user_id`, `user_prompt`, `generated_sql`, `sanitized_sql`, `execution_status`, `execution_time_ms`, `rows_returned`, `error_message`

---

## 3. The 5-Gate Defense-in-Depth Implementation Details

### Gate 1: Minimal Schema Selection
- Gemini is only supplied with schema definitions for verified operational tables (`departments`, `employees`, `vendors`, `contracts`, `invoices`, `operational_expenses`).
- System tables and security-critical entities (`users`, `documents`, `document_chunks`) are completely omitted from the prompt, reducing hallucination surface and unauthorized query attempts.

### Gate 2: AST Parsing & Single Statement Verification
- Uses `sqlglot.parse(clean_sql, read="postgres")`.
- Rejects queries that fail syntax validation, contain zero statements, or contain multiple statements separated by semicolons (`len(parsed) != 1`).
- Ensures the root node is strictly `sqlglot.expressions.Select`. Any `Insert`, `Update`, `Delete`, `Drop`, or other DDL/DML nodes trigger an immediate `SQLSecurityViolation`.

### Gate 3: Table Whitelisting & Prohibited Functions Sandbox
- Traverses all `exp.Table` nodes in the AST and asserts every table referenced is contained within `ALLOWED_TABLES`.
- Any attempt to query unwhitelisted tables (`users`, `documents`, `pg_catalog.pg_tables`) is rejected before reaching the database.
- Traverses all `(exp.Func, exp.Anonymous)` nodes to block denial-of-service or fingerprinting functions (`pg_sleep`, `version`, `current_user`, `current_database`, `inet_client_addr`).

### Gate 4: Multi-Tenant AST Injection & Read-Only Transactions
- For every referenced table in the AST, automatically injects a `WHERE alias.tenant_id = '<tenant_id>'` predicate via `expr.where()`.
- Executes within an explicit PostgreSQL read-only transaction: `SET TRANSACTION READ ONLY;`.
- Followed by a cleanup `await db.rollback()` in a `finally` block to release the transaction so subsequent audit log writes succeed.

### Gate 5: Execution Guardrails & Timeouts
- Searches for `exp.Limit`. If missing, injects `LIMIT 100`. If present and exceeding 100 or non-positive, caps the value to 100.
- Sets a strict session statement timeout: `SET statement_timeout = 3000;` (3 seconds) to prevent expensive table scans or Cartesian joins.

---

## 4. Key Architectural Decisions & Trade-offs

### Decision 1: AST Parsing via `sqlglot` vs. Regex or Rule Matching
- **Context:** Detecting SQL injection, destructive statements, or unauthorized tables in raw SQL strings is notoriously prone to bypasses (e.g. comments, obfuscation, case manipulation, newline injections).
- **Decision:** Parse candidate SQL into a true Abstract Syntax Tree (AST) using `sqlglot` configured for the `postgres` dialect.
- **Trade-off:** Minimal AST parsing overhead (~2–5ms) in exchange for mathematical, semantic certainty over query structure and table references.

### Decision 2: AST-Level Tenant Filter Injection vs. PostgreSQL Row-Level Security (RLS)
- **Context:** Multi-tenancy must be strictly enforced.
- **Decision:** Inject `alias.tenant_id = :tenant_id` directly into the query AST before execution, supplemented by connection-level tenant isolation.
- **Trade-off:** AST injection makes tenant scoping transparent and verifiable in the audit logs without requiring dynamic database role switching per query.

### Decision 3: Transaction Isolation and Audit Logging Resiliency
- **Context:** Running `SET TRANSACTION READ ONLY;` protects against accidental or malicious writes. However, PostgreSQL read-only transactions disallow subsequent `INSERT INTO sql_query_audit_logs`.
- **Decision:** Execute the read query, fetch rows, and explicitly terminate the read-only transaction block (`await db.rollback()`) within a `finally` block before persisting the audit record. Furthermore, extract scalar user attributes (`user_id`, `tenant_id`) into Python strings upfront to prevent SQLAlchemy `MissingGreenlet` lazy-loading errors after transaction rollbacks.
- **Trade-off:** Requires careful session transaction state management, but guarantees tamper-evident audit logging for every query attempt (success, blocked, or error).

---

## 5. Verification & Test Metrics

- **Unit & Sandbox Test Suite (`tests/unit/test_sql.py`):**
  - `test_sql_sandbox_rejects_non_select`: PASSED
  - `test_sql_sandbox_rejects_multi_statement`: PASSED
  - `test_sql_sandbox_rejects_unwhitelisted_tables`: PASSED
  - `test_sql_sandbox_rejects_prohibited_functions`: PASSED
  - `test_sql_sandbox_enforces_tenant_filter_and_limit`: PASSED
  - `test_text_to_sql_api_and_audit_flow`: PASSED
- **Full Platform Test Suite (`pytest tests/ -v`):**
  - **12/12 passed (100% green)** across Authentication, Config, Document Ingestion, Health, Grounded RAG, Hybrid Retrieval, and Text-to-SQL.

---

## 6. Staff/Principal Engineer Interview Defense

### Q1: Why not rely on the LLM's system prompt to enforce read-only and tenant boundaries?
> **Answer:** Relying on system prompts for security boundaries is an anti-pattern known as "prompt-level security," which is vulnerable to adversarial jailbreaks, indirect prompt injection (e.g. malicious values in document chunks), and model hallucination. Our architecture treats the LLM strictly as an untrusted query generator. Security is enforced deterministically downstream through AST validation (`sqlglot`), schema whitelisting, AST tenant injection, and database-level read-only transactions. Even if the LLM generates `DROP TABLE`, Gate 2 stops execution prior to touching the database.

### Q2: How does the platform prevent denial-of-service via computationally expensive SQL queries?
> **Answer:** We enforce two independent layers:
> 1. **AST Limit Capping (Gate 5):** Guarantees that no query can return unbound result sets; queries without a `LIMIT` or with `LIMIT > 100` are capped to 100 rows.
> 2. **Session Statement Timeout (Gate 5):** `SET statement_timeout = 3000;` instructs PostgreSQL's query planner and engine to abort any query taking longer than 3,000 milliseconds. This neutralizes runaway queries such as accidental Cartesian cross-joins.

### Q3: What happens when an operational query fails or is blocked by the security sandbox?
> **Answer:** All queries—whether successful, blocked by security gates (`BLOCKED`), or rejected by PostgreSQL (`ERROR`)—are recorded in `sql_query_audit_logs` with execution timing, user ID, tenant ID, and the root cause error message. This provides full observability, intrusion detection capability, and compliance traceability.
