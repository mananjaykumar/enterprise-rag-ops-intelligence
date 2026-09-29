import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.operational import Department, Vendor
from src.db.session import engine
from src.services.sql_sandbox import SQLSandboxService, SQLSecurityViolation

# =========================================================================
# 1. 5-GATE DEFENSE-IN-DEPTH SANDBOX UNIT TESTS
# =========================================================================


def test_sql_sandbox_rejects_non_select():
    """Gate 2: Verify destructive DDL/DML statements are immediately blocked."""
    sandbox = SQLSandboxService()

    with pytest.raises(SQLSecurityViolation, match="Destructive operation rejected"):
        sandbox.validate_and_sanitize("UPDATE departments SET annual_budget = 0", "t1")

    with pytest.raises(SQLSecurityViolation, match="Destructive operation rejected"):
        sandbox.validate_and_sanitize("DROP TABLE departments", "t1")

    with pytest.raises(SQLSecurityViolation, match="Destructive operation rejected"):
        sandbox.validate_and_sanitize("DELETE FROM operational_expenses", "t1")

    with pytest.raises(SQLSecurityViolation, match="Destructive operation rejected"):
        sandbox.validate_and_sanitize(
            "INSERT INTO departments (code, name) VALUES ('X', 'Y')", "t1"
        )


def test_sql_sandbox_rejects_multi_statement():
    """Gate 2: Verify semicolon query chaining is blocked."""
    sandbox = SQLSandboxService()

    with pytest.raises(SQLSecurityViolation, match="Multi-statement execution rejected"):
        sandbox.validate_and_sanitize(
            "SELECT name FROM departments; DROP TABLE operational_expenses;", "t1"
        )


def test_sql_sandbox_rejects_unwhitelisted_tables():
    """Gate 3: Verify queries accessing users, documents, or pg_catalog are blocked."""
    sandbox = SQLSandboxService()

    with pytest.raises(SQLSecurityViolation, match="restricted or non-whitelisted tables"):
        sandbox.validate_and_sanitize("SELECT email, hashed_password FROM users", "t1")

    with pytest.raises(SQLSecurityViolation, match="restricted or non-whitelisted tables"):
        sandbox.validate_and_sanitize("SELECT * FROM documents", "t1")

    with pytest.raises(SQLSecurityViolation, match="restricted or non-whitelisted tables"):
        sandbox.validate_and_sanitize("SELECT * FROM document_chunks", "t1")

    with pytest.raises(SQLSecurityViolation, match="restricted or non-whitelisted tables"):
        sandbox.validate_and_sanitize("SELECT tablename FROM pg_catalog.pg_tables", "t1")


def test_sql_sandbox_rejects_prohibited_functions():
    """Gate 3: Verify execution denial-of-service functions like pg_sleep are blocked."""
    sandbox = SQLSandboxService()

    with pytest.raises(SQLSecurityViolation, match="Forbidden SQL function"):
        sandbox.validate_and_sanitize("SELECT pg_sleep(10) FROM departments", "t1")

    with pytest.raises(SQLSecurityViolation, match="Forbidden SQL function"):
        sandbox.validate_and_sanitize("SELECT version() FROM departments", "t1")


def test_sql_sandbox_enforces_tenant_filter_and_limit():
    """Gate 4 & 5: Verify automatic tenant injection and limit capping."""
    sandbox = SQLSandboxService()

    # Case A: Query without tenant filter and without LIMIT
    sanitized = sandbox.validate_and_sanitize(
        "SELECT name, annual_budget FROM departments", "tenant_alpha"
    )
    assert "departments.tenant_id = 'tenant_alpha'" in sanitized
    assert "LIMIT 100" in sanitized

    # Case B: Query with excessive LIMIT 500 capped to 100
    sanitized_capped = sandbox.validate_and_sanitize(
        "SELECT name FROM departments d WHERE d.annual_budget > 1000 LIMIT 500", "tenant_alpha"
    )
    assert "d.tenant_id = 'tenant_alpha'" in sanitized_capped
    assert "LIMIT 100" in sanitized_capped


# =========================================================================
# 2. END-TO-END TEXT-TO-SQL API INTEGRATION TESTS
# =========================================================================


@pytest.mark.asyncio
async def test_text_to_sql_api_and_audit_flow(async_client: AsyncClient):
    """Verifies natural language to SQL generation, execution, tenant isolation, and audit logging."""
    random_id = uuid.uuid4().hex[:6]
    tenant_a = f"tenant_sql_a_{random_id}"
    tenant_b = f"tenant_sql_b_{random_id}"

    user_a_email = f"analyst_sql_{random_id}@corp.com"
    user_b_email = f"other_sql_{random_id}@othercorp.com"
    password = "SecurePassword123!"

    # 1. Register test users
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_a_email,
            "password": password,
            "full_name": "SQL Analyst A",
            "role": "analyst",
            "tenant_id": tenant_a,
        },
    )
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_b_email,
            "password": password,
            "full_name": "SQL Analyst B",
            "role": "analyst",
            "tenant_id": tenant_b,
        },
    )

    # 2. Login
    login_a = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user_a_email, "password": password, "tenant_id": tenant_a},
    )
    token_a = login_a.json()["access_token"]

    login_b = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user_b_email, "password": password, "tenant_id": tenant_b},
    )
    token_b = login_b.json()["access_token"]

    # 3. Seed operational business data in tenant_a
    dept_code = f"ENG_{random_id}"
    async with AsyncSession(engine) as session:
        dept_eng = Department(
            id=uuid.uuid4(),
            tenant_id=tenant_a,
            code=dept_code,
            name="Engineering",
            annual_budget=Decimal("1500000.00"),
        )
        dept_mkt = Department(
            id=uuid.uuid4(),
            tenant_id=tenant_a,
            code=f"MKT_{random_id}",
            name="Marketing",
            annual_budget=Decimal("450000.00"),
        )
        vendor_acme = Vendor(
            id=uuid.uuid4(),
            tenant_id=tenant_a,
            vendor_code=f"ACME_{random_id}",
            name="Acme Cloud Technologies",
            category="Software",
            risk_rating="LOW",
            is_active=True,
        )
        session.add_all([dept_eng, dept_mkt, vendor_acme])
        await session.commit()
        prompt_q = f"What is the annual budget and name of the department with code '{dept_code}'?"

    # 4. Unauthenticated request -> 401 Unauthorized
    unauth_resp = await async_client.post(
        "/api/v1/sql/query",
        json={"prompt": prompt_q},
    )
    assert unauth_resp.status_code == 401

    # 5. Execute Natural Language SQL query as user A
    query_resp = await async_client.post(
        "/api/v1/sql/query",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "prompt": prompt_q,
            "explain": True,
        },
    )
    assert query_resp.status_code == 200
    data = query_resp.json()
    assert "generated_sql" in data
    assert "sanitized_sql" in data
    assert "Engineering" in str(data["rows"])
    assert data["row_count"] >= 1
    assert data["execution_time_ms"] > 0
    assert data["explanation"] is not None

    # 6. Cross-Tenant Isolation: User B in tenant_b queries the same question -> MUST return 0 rows
    query_resp_b = await async_client.post(
        "/api/v1/sql/query",
        headers={"Authorization": f"Bearer {token_b}"},
        json={
            "prompt": prompt_q,
            "explain": False,
        },
    )
    assert query_resp_b.status_code == 200
    data_b = query_resp_b.json()
    assert data_b["row_count"] == 0
    assert len(data_b["rows"]) == 0

    # 7. Audit log verification
    audit_resp = await async_client.get(
        "/api/v1/sql/audit-logs",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    latest_log = logs[0]
    assert latest_log["tenant_id"] == tenant_a
    assert latest_log["execution_status"] == "SUCCESS"
    assert latest_log["rows_returned"] >= 1
