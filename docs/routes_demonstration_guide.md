# Enterprise RAG & Operations Intelligence Platform
## Demonstration Guide: Routing Architecture & Execution Pathways

This document provides a comprehensive operational guide to the platform's multi-path execution engine, detailing the schema relationships, the unified seed script, the admin credentials, and concrete demo queries for each of the three primary routes: **SQL**, **RAG**, and **HYBRID_AGENT**.

---

## 1. Authentication & System Access

The database seed script initializes a dedicated enterprise administrator user:

- **Email**: `admin@gmail.com`
- **Password**: `Admin@12345`
- **Role**: `admin`
- **Tenant ID**: `default_tenant`

### Generating an Access Token
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@gmail.com","password":"Admin@12345"}'
```

---

## 2. Operational Database Architecture (Structured Data)

The operational database schema models an enterprise business ecosystem without depending on external file uploads.

```
                    +--------------------+
                    |    departments     |
                    +--------------------+
                    | id (PK)            |
                    | code (ENG, MKT...) |
                    | name               |
                    | annual_budget      |
                    +---------+----------+
                              | 1
                              |
                              | M
                    +---------v----------+
                    |     employees      |
                    +--------------------+
                    | id (PK)            |
                    | department_id (FK) |
                    | employee_code      |
                    | full_name          |
                    | role_title         |
                    | employment_status  |
                    +---------+----------+
                              | 1
                              |
       +----------------------+----------------------+
       | M                                           | M
+------v-------------------+            +------------v--------------+
|   operational_expenses   |            |         invoices          |
+--------------------------+            +---------------------------+
| id (PK)                  |            | id (PK)                   |
| department_id (FK)       |            | vendor_id (FK)            |
| employee_id (FK)         |            | contract_id (FK, nullable)|
| category (Software, etc.)|            | invoice_number            |
| amount                   |            | amount                    |
| expense_date             |            | payment_status            |
| approved (BOOLEAN)       |            +------------^--------------+
+--------------------------+                         | M
                                                     |
                                        +------------+--------------+
                                        |         contracts         |
                                        +---------------------------+
                                        | id (PK)                   |
                                        | vendor_id (FK)            |
                                        | contract_number           |
                                        | total_value               |
                                        | start_date / end_date     |
                                        | status (ACTIVE, EXPIRED)  |
                                        +------------^--------------+
                                                     | M
                                                     |
                                        +------------+--------------+
                                        |          vendors          |
                                        +---------------------------+
                                        | id (PK)                   |
                                        | vendor_code               |
                                        | name                      |
                                        | category (Software, etc.) |
                                        | risk_rating (LOW, MED, HI)|
                                        | is_active (BOOLEAN)       |
                                        +---------------------------+
```

### Seeding Command
Run the standalone database seeding script anytime to populate or reset these tables:
```bash
.venv/bin/python scripts/seed_operational_data.py
```

### Seeded Relational Datasets
| Entity | Count | Key Records / Samples |
|---|---|---|
| **Departments** | 5 | Engineering ($1.8M budget), Marketing ($950k), Finance ($600k), People Ops ($400k), Cybersecurity ($750k) |
| **Employees** | 11 | Alex Chen (Cloud Architect), Sarah Connor (Data Eng), Kavita Rao (CISO), Jessica Taylor (VP Growth), etc. |
| **Vendors** | 6 | CloudScale Systems (LOW risk), CyberFort Defense (LOW risk), DataFlow AI (MED risk), Apex Freight (MED risk), Beacon Strategy Consulting (HIGH risk), OmniWorkspace Supplies (Inactive) |
| **Contracts** | 5 | Cloud Hosting ($320k), SOC / Pentesting ($140k), AI Feature Store ($90k, Expired), Freight Warehousing ($185k), Strategy Advisory ($75k) |
| **Invoices** | 11 | Invoices tracking contract caps, overdue payments, and Beacon Consulting exceeding contract cap by $10k |
| **Operational Expenses** | 19 | Cross-department software subscriptions, travel expenditures, hardware supplies, and unapproved expense flags |

---

## 3. The Three Execution Routes

```
                             User Prompt
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │ QueryRouterService  │
                       │ (Fast Pre-filter +  │
                       │   LLM Fallback)     │
                       └──────────┬──────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
  │  SQL Route   │         │  RAG Route   │         │ HYBRID_AGENT │
  │ (Structured) │         │(Unstructured)│         │ (Parallel    │
  └──────────────┘         └──────────────┘         │  RAG + SQL)  │
                                                    └──────────────┘
```

---

## Route 1: Direct SQL Route

### Definition & Purpose
Used when the user's intent is to inspect operational metrics, tabular aggregations, employee directories, invoices, budgets, or vendor relationships residing in the PostgreSQL relational schema.

### Execution Path
1. **Router**: Identifies tabular intent (keywords like `budget`, `vendor`, `invoice`, `expense`, `department`, `how many`, `total amount`).
2. **TextToSQLService**: Translates the question into strict read-only PostgreSQL syntax with tenant filters.
3. **5-Gate Sandbox**: Validates AST, ensures no mutations (`INSERT`/`DELETE`), verifies whitelist tables, enforces tenant isolation clause, and injects `LIMIT 100`.
4. **Execution & Explanation**: Runs in `<50ms` and returns formatted data with natural language summary.

### Example Queries for Demonstration

#### Example 1.1: Aggregation & Join Across Departments
- **Query Prompt**: `"What is the total operational expense per department?"`
- **Router Choice**: `SQL`
- **Generated SQL**:
  ```sql
  SELECT d.name AS department_name, SUM(oe.amount) AS total_expenses
  FROM departments AS d
  JOIN operational_expenses AS oe ON d.id = oe.department_id
  WHERE d.tenant_id = 'default_tenant' AND oe.tenant_id = 'default_tenant'
  GROUP BY d.id, d.name
  LIMIT 100;
  ```
- **Result Highlight**:
  - Cybersecurity & Compliance: $33,900.00
  - Marketing & Growth: $30,120.00
  - Engineering & Infrastructure: $29,030.00
  - Finance & Accounting: $14,800.00
  - People Operations & HR: $11,550.00

#### Example 1.2: Status & Risk Filter
- **Query Prompt**: `"List all active vendors and their risk ratings"`
- **Router Choice**: `SQL`
- **Generated SQL**:
  ```sql
  SELECT name, risk_rating FROM vendors WHERE is_active = TRUE;
  ```
- **Result Highlight**: Returns 5 active vendors (CloudScale Systems [LOW], CyberFort Defense [LOW], DataFlow AI [MED], Apex Freight [MED], Beacon Strategy [HIGH]). Excludes the inactive vendor OmniWorkspace Supplies.

#### Example 1.3: Anomaly & Overdue Invoice Auditing
- **Query Prompt**: `"Show all overdue invoices with their vendor names and amounts"`
- **Router Choice**: `SQL`
- **Generated SQL**:
  ```sql
  SELECT v.name, i.invoice_number, i.amount, i.due_date
  FROM invoices i
  JOIN vendors v ON i.vendor_id = v.id
  WHERE i.payment_status = 'OVERDUE';
  ```
- **Result Highlight**: Flags invoice `INV-SEC-202` ($70,000.00) from CyberFort Defense due on 2025-01-15.

---

## Route 2: Direct RAG Route

### Definition & Purpose
Used when the user's intent queries qualitative knowledge, unstructured policies, employee handbooks, travel limits, SOPs, or legal contracts stored as text documents in the PGVector vector database.

### Execution Path
1. **Router**: Detects unstructured policy keywords (`policy`, `guideline`, `procedure`, `rule`, `allowance`, `per diem`, `handbook`).
2. **Dense + Sparse Hybrid Search**: Generates 768-dim query embedding and executes Reciprocal Rank Fusion (RRF) across semantic and full-text indexes.
3. **Cross-Encoder Reranker**: Re-scores top-k chunks for high precision.
4. **Answer Generation**: Generates synthesis citing document titles and chunk IDs.

### Example Queries for Demonstration

#### Example 2.1: Corporate Travel Allowance Policy
- **Query Prompt**: `"What is the maximum daily meal allowance for domestic travel under Tier 1 cities?"`
- **Router Choice**: `RAG`
- **Retrieved Chunks**: `indian_corporate_travel_and_daily_allowance_policy.md` (Section 4: Daily Allowances & Meals).
- **Result Highlight**: Explains the exact per diem allowances categorized by city tier and role grades (e.g. ₹1,500/day for Tier 1 metropolitans) with direct citations.

#### Example 2.2: Remote Work & Equipment Guidelines
- **Query Prompt**: `"What is our remote work policy regarding home office reimbursement?"`
- **Router Choice**: `RAG`
- **Result Highlight**: Returns policy guidelines detailing workstation setup allowances, eligible peripheral accessories, and submission windows.

#### Example 2.3: Contract Renewal & Cancellation Clauses
- **Query Prompt**: `"What are the termination notice requirements specified in our standard vendor agreement?"`
- **Router Choice**: `RAG`
- **Result Highlight**: Cites contractual terms requiring 30-day written notice for termination without cause.

---

## Route 3: HYBRID_AGENT Route

### Definition & Purpose
Used when a single inquiry cannot be answered by either database or documents alone. It bridges policy rules (RAG) with real-world spending/invoices (SQL) to uncover compliance violations, budget variance, or audit anomalies.

### Execution Path (Optimized Concurrent Pipeline)
1. **Router**: Detects comparative / cross-boundary intent (`compare`, `vs policy`, `exceeding`, `compliant with`, `audit`).
2. **Parallel Node (`asyncio.gather`)**:
   - Branch A runs RAG retrieval against policy documents.
   - Branch B translates and executes the SQL query against operational tables.
   - Both execute concurrently in **~12–15 seconds** (50% latency reduction from sequential chains).
3. **Synthesis Node**: Synthesizes the quantitative database metrics with the qualitative policy provisions, highlighting compliance gaps and citing both data sources.

### Example Queries for Demonstration

#### Example 3.1: Expense Compliance Audit
- **Query Prompt**: `"Compare Alex Chen's travel expenses against the corporate travel policy allowance"`
- **Router Choice**: `HYBRID_AGENT`
- **Execution**:
  - **SQL**: Retrieves Alex Chen's travel expense record ($3,450.00 for AWS re:Invent flights and registration).
  - **RAG**: Retrieves conference travel policy limits and international travel approval protocols from the Travel Policy document.
  - **Synthesis**: Reconciles the flight costs and conference fee against authorized expense caps, confirming whether executive pre-approval was required.

#### Example 3.2: Vendor Invoice vs Contract Ceiling
- **Query Prompt**: `"Audit Beacon Strategy Consulting invoices against their approved contract value and policy limits"`
- **Router Choice**: `HYBRID_AGENT`
- **Execution**:
  - **SQL**: Finds Contract `CTR-2024-005` value is $75,000.00, but total billed invoices (`INV-CNS-301` + `INV-CNS-302`) total $85,000.00.
  - **RAG**: Retrieves procurement policy rules on contract variation limits and purchase order overages.
  - **Synthesis**: Highlights that Beacon Strategy Consulting has exceeded their authorized contract limit by $10,000 (13.3% overrun), flagging it as an unauthorized procurement over-expenditure.

#### Example 3.3: Department Budget Utilization vs Guidelines
- **Query Prompt**: `"Which departments have spent more than 50% of their operational budget on software licenses, and does this comply with IT procurement guidelines?"`
- **Router Choice**: `HYBRID_AGENT`
- **Execution**:
  - **SQL**: Aggregates software expenses by department and compares to each department's `annual_budget`.
  - **RAG**: Retrieves IT software procurement governance and multi-year subscription guidelines.
  - **Synthesis**: Combines the percentage spend with IT procurement requirements for vendor consolidation.

---

## 4. API Query Examples

You can test any route directly using `curl` against `/api/v1/agent/query`:

```bash
# 1. Obtain token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@gmail.com","password":"Admin@12345"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 2. Test SQL Route
curl -s -X POST http://localhost:8000/api/v1/agent/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"List all active vendors and their risk ratings"}'

# 3. Test RAG Route
curl -s -X POST http://localhost:8000/api/v1/agent/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is the per diem meal allowance in the travel policy?"}'

# 4. Test Hybrid Route
curl -s -X POST http://localhost:8000/api/v1/agent/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Audit Beacon Consulting invoices against their contract limit and corporate policy"}'
```
