import datetime
import hashlib
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.db.models.document import Document, DocumentChunk, DocumentLifecycleStatus
from src.db.models.operational import Department, Employee, OperationalExpense
from src.db.session import engine
from src.infrastructure.ai.gemini import GeminiEmbeddingClient
from src.schemas.agent import ExecutionRoute
from src.services.router import QueryRouterService

settings = get_settings()


# =========================================================================
# 1. INTENT ROUTER UNIT TESTS
# =========================================================================


@pytest.mark.asyncio
async def test_query_router_classification():
    """Verifies precision of the Intent Classifier across RAG, SQL, and Hybrid pathways."""
    router = QueryRouterService()

    # Case A: Document Policy Intent -> RAG
    route_rag, reason_rag = await router.route_query(
        "What is our company remote work and equipment security policy?"
    )
    assert route_rag == ExecutionRoute.RAG
    assert len(reason_rag) > 0

    # Case B: Operational Structured Intent -> SQL
    route_sql, reason_sql = await router.route_query(
        "What is the total annual budget allocated to the Engineering department?"
    )
    assert route_sql == ExecutionRoute.SQL
    assert len(reason_sql) > 0

    # Case C: Cross-Referencing Compliance Intent -> HYBRID_AGENT
    route_hybrid, reason_hybrid = await router.route_query(
        "Compare our travel policy daily allowance limits with actual Engineering expenses to find non-compliant claims."
    )
    assert route_hybrid == ExecutionRoute.HYBRID_AGENT
    assert len(reason_hybrid) > 0

    # Case D: Manual Override Bypass
    route_forced, _ = await router.route_query("Any question", force_route=ExecutionRoute.SQL)
    assert route_forced == ExecutionRoute.SQL


# =========================================================================
# 2. END-TO-END AGENT ORCHESTRATOR INTEGRATION TESTS
# =========================================================================


@pytest.mark.asyncio
async def test_agent_api_hybrid_orchestration_and_isolation(async_client: AsyncClient):
    """Verifies multi-step LangGraph reasoning, document + database cross-referencing, and tenant isolation."""
    random_id = uuid.uuid4().hex[:6]
    tenant_a = f"tenant_agent_a_{random_id}"
    tenant_b = f"tenant_agent_b_{random_id}"

    user_a_email = f"lead_analyst_{random_id}@corp.com"
    user_b_email = f"other_analyst_{random_id}@othercorp.com"
    password = "SecurePassword123!"

    # 1. Register test users
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_a_email,
            "password": password,
            "full_name": "Lead Analyst A",
            "role": "analyst",
            "tenant_id": tenant_a,
        },
    )
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_b_email,
            "password": password,
            "full_name": "Other Analyst B",
            "role": "analyst",
            "tenant_id": tenant_b,
        },
    )

    # 2. Authenticate
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

    # 3. Seed unstructured document knowledge in tenant_a: Corporate Travel Policy
    embedder = GeminiEmbeddingClient()
    policy_content = (
        "Corporate Travel and Expense Policy 2025:\n"
        "Section 4.1: Lodging and Accommodation.\n"
        "The standard daily spending allowance limit for employee hotel lodging is exactly $200.00 per night. "
        "Any employee lodging expense claim exceeding $200.00 per day without prior executive approval is strictly non-compliant."
    )
    policy_embeddings = await embedder.embed_documents([policy_content])
    policy_vector = policy_embeddings[0]

    doc_id = uuid.uuid4()
    dept_id = uuid.uuid4()
    emp_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    dept_code = f"ENG_{random_id}"
    emp_code = f"EMP_{random_id}"

    async with AsyncSession(engine) as session:
        # A. Create Policy Document
        doc = Document(
            id=doc_id,
            tenant_id=tenant_a,
            title="Corporate Travel and Expense Policy",
            filename="travel_policy.md",
            storage_path="/data/policies/travel_policy.md",
            file_hash_sha256=hashlib.sha256(policy_content.encode()).hexdigest(),
            mime_type="text/markdown",
            size_bytes=len(policy_content),
            version=1,
            status=DocumentLifecycleStatus.ACTIVE,
            is_active=True,
            allowed_roles=["analyst", "manager", "admin"],
            doc_metadata={"category": "Policy"},
        )
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_id,
            tenant_id=tenant_a,
            chunk_index=0,
            content=policy_content,
            content_hash=hashlib.sha256(policy_content.encode()).hexdigest(),
            allowed_roles=["analyst", "manager", "admin"],
            is_active=True,
            embedding_model=settings.ACTIVE_EMBEDDING_MODEL,
            embedding_dimension=768,
            embedding=policy_vector,
            heading_hierarchy=["Corporate Travel", "Lodging Allowance"],
            section_heading="Lodging Limits",
            chunk_type="text",
            table_metadata={},
        )
        session.add_all([doc, chunk])

        # B. Seed Relational Business Tables in tenant_a
        dept = Department(
            id=dept_id,
            tenant_id=tenant_a,
            code=dept_code,
            name="Engineering",
            annual_budget=Decimal("500000.00"),
        )
        emp = Employee(
            id=emp_id,
            department_id=dept_id,
            tenant_id=tenant_a,
            employee_code=emp_code,
            full_name="John Engineer",
            email=f"john_{random_id}@corp.com",
            role_title="Senior Infrastructure Architect",
            employment_status="ACTIVE",
            hire_date=datetime.date(2023, 1, 15),
        )
        # Expense: $350.00 lodging claim (violating the $200.00 limit!)
        expense = OperationalExpense(
            id=exp_id,
            department_id=dept_id,
            employee_id=emp_id,
            tenant_id=tenant_a,
            category="Travel",
            amount=Decimal("350.00"),
            currency="USD",
            expense_date=datetime.date(2025, 4, 10),
            description="Conference hotel lodging in New York",
            approved=True,
        )
        session.add_all([dept, emp, expense])
        await session.commit()

    prompt_q = (
        f"Compare our travel policy daily lodging allowance limit with actual lodging expenses for department '{dept_code}' "
        f"to identify any non-compliant claims."
    )

    # 4. Unauthenticated request -> 401 Unauthorized
    unauth_resp = await async_client.post(
        "/api/v1/agent/query",
        json={"prompt": prompt_q},
    )
    assert unauth_resp.status_code == 401

    # 5. Execute Hybrid Agent query as User A in tenant_a
    agent_resp = await async_client.post(
        "/api/v1/agent/query",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "prompt": prompt_q,
            "force_route": "HYBRID_AGENT",
        },
    )
    assert agent_resp.status_code == 200
    data = agent_resp.json()

    assert data["route_selected"] == "HYBRID_AGENT"
    assert len(data["plan_steps"]) >= 3
    # Check that plan steps progressed
    actions = [s["action"] for s in data["plan_steps"]]
    assert "RETRIEVE_DOCUMENTS" in actions
    assert "QUERY_DATABASE" in actions
    assert "SYNTHESIZE_REPORT" in actions

    # Document citations present
    assert len(data["citations"]) >= 1
    assert "Travel and Expense Policy" in data["citations"][0]["document_title"]

    # Database SQL results present
    assert len(data["sql_results"]) >= 1
    assert "350" in str(data["sql_results"][0]["rows"])

    # Synthesis identifies the $200 limit and the $350 claim
    answer = data["answer"]
    assert "200" in answer
    assert "350" in answer
    assert data["execution_time_ms"] > 0

    # 6. Cross-Tenant Isolation: User B in tenant_b runs the exact same query
    agent_resp_b = await async_client.post(
        "/api/v1/agent/query",
        headers={"Authorization": f"Bearer {token_b}"},
        json={
            "prompt": prompt_q,
            "force_route": "HYBRID_AGENT",
        },
    )
    assert agent_resp_b.status_code == 200
    data_b = agent_resp_b.json()
    # Must NOT have any citations or rows from tenant_a
    assert len(data_b["citations"]) == 0
    if data_b["sql_results"]:
        assert len(data_b["sql_results"][0]["rows"]) == 0
