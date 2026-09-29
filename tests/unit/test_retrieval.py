import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.db.models.document import Document, DocumentChunk, DocumentLifecycleStatus
from src.db.session import engine
from src.infrastructure.ai.gemini import GeminiEmbeddingClient

settings = get_settings()


@pytest.mark.asyncio
async def test_hybrid_retrieval_and_rbac_isolation(async_client: AsyncClient):
    """Verifies hybrid search, hard security pre-filtering, RRF, and cross-tenant isolation."""
    random_id = uuid.uuid4().hex[:6]
    tenant_a = f"tenant_a_{random_id}"
    tenant_b = f"tenant_b_{random_id}"

    analyst_email = f"analyst_rag_{random_id}@corp.com"
    manager_email = f"manager_rag_{random_id}@corp.com"
    other_tenant_email = f"other_rag_{random_id}@othercorp.com"
    password = "SecurePassword123!"

    # 1. Register test accounts
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": analyst_email,
            "password": password,
            "full_name": "RAG Analyst",
            "role": "analyst",
            "tenant_id": tenant_a,
        },
    )
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": manager_email,
            "password": password,
            "full_name": "RAG Manager",
            "role": "manager",
            "tenant_id": tenant_a,
        },
    )
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": other_tenant_email,
            "password": password,
            "full_name": "Other Tenant User",
            "role": "manager",
            "tenant_id": tenant_b,
        },
    )

    # 2. Acquire JWT tokens
    analyst_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": analyst_email, "password": password, "tenant_id": tenant_a},
    )
    analyst_token = analyst_resp.json()["access_token"]

    manager_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": manager_email, "password": password, "tenant_id": tenant_a},
    )
    manager_token = manager_resp.json()["access_token"]

    other_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": other_tenant_email, "password": password, "tenant_id": tenant_b},
    )
    other_token = other_resp.json()["access_token"]

    # 3. Seed active documents & chunks with live Gemini embeddings
    embedding_client = GeminiEmbeddingClient()
    policy_text = "All company laptops must run disk encryption and use 16-character passwords."
    cafe_text = "The corporate cafeteria serves fresh sandwiches and salads daily at 12pm."

    policy_vec = await embedding_client.embed_query(policy_text)
    cafe_vec = await embedding_client.embed_query(cafe_text)

    async with AsyncSession(engine) as session:
        # Document 1: Restricted IT Policy (Admin & Manager only)
        doc_policy = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_a,
            title="Corporate IT Security Policy",
            filename="it_policy.md",
            storage_path="/data/dummy/it_policy.md",
            file_hash_sha256="hash_policy",
            mime_type="text/markdown",
            size_bytes=len(policy_text),
            version=1,
            status=DocumentLifecycleStatus.ACTIVE,
            is_active=True,
            allowed_roles=["admin", "manager"],
            doc_metadata={},
        )
        session.add(doc_policy)

        chunk_policy = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_policy.id,
            tenant_id=tenant_a,
            chunk_index=0,
            content=policy_text,
            content_hash=hashlib.sha256(policy_text.encode()).hexdigest(),
            allowed_roles=["admin", "manager"],
            is_active=True,
            embedding_model=settings.ACTIVE_EMBEDDING_MODEL,
            embedding_dimension=768,
            embedding=policy_vec,
            heading_hierarchy=["IT Security", "Laptops"],
            section_heading="Laptop Encryption",
            chunk_type="text",
            table_metadata={},
        )
        session.add(chunk_policy)

        # Document 2: General Cafeteria Guide (All roles: Admin, Manager, Analyst)
        doc_cafe = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_a,
            title="Office Cafeteria Guidelines",
            filename="cafe_guide.md",
            storage_path="/data/dummy/cafe_guide.md",
            file_hash_sha256="hash_cafe",
            mime_type="text/markdown",
            size_bytes=len(cafe_text),
            version=1,
            status=DocumentLifecycleStatus.ACTIVE,
            is_active=True,
            allowed_roles=["admin", "manager", "analyst"],
            doc_metadata={},
        )
        session.add(doc_cafe)

        chunk_cafe = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_cafe.id,
            tenant_id=tenant_a,
            chunk_index=0,
            content=cafe_text,
            content_hash=hashlib.sha256(cafe_text.encode()).hexdigest(),
            allowed_roles=["admin", "manager", "analyst"],
            is_active=True,
            embedding_model=settings.ACTIVE_EMBEDDING_MODEL,
            embedding_dimension=768,
            embedding=cafe_vec,
            heading_hierarchy=["Cafeteria"],
            section_heading="Hours & Menu",
            chunk_type="text",
            table_metadata={},
        )
        session.add(chunk_cafe)

        await session.commit()

    # 4. Unauthenticated search -> 401 Unauthorized
    unauth_resp = await async_client.post(
        "/api/v1/retrieval/search",
        json={"query": "laptop disk encryption"},
    )
    assert unauth_resp.status_code == 401

    # 5. RBAC Hard Security Pre-Filter: Analyst searches for IT Security
    # MUST return 0 results because Analyst is not in allowed_roles for it_policy!
    analyst_search = await async_client.post(
        "/api/v1/retrieval/search",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"query": "laptop disk encryption passwords", "top_n": 5},
    )
    assert analyst_search.status_code == 200
    analyst_results = analyst_search.json()["results"]
    for chunk in analyst_results:
        assert chunk["source"]["filename"] != "it_policy.md"

    # 6. Manager searches for IT Security -> MUST retrieve it_policy!
    manager_search = await async_client.post(
        "/api/v1/retrieval/search",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"query": "laptop disk encryption passwords", "top_n": 5},
    )
    assert manager_search.status_code == 200
    manager_results = manager_search.json()["results"]
    assert len(manager_results) > 0
    top_hit = manager_results[0]
    assert top_hit["source"]["filename"] == "it_policy.md"
    assert "encryption" in top_hit["content"]
    assert top_hit["rrf_score"] > 0.0
    assert top_hit["rerank_score"] is not None
    assert top_hit["source"]["section_heading"] == "Laptop Encryption"

    # 7. Cross-Tenant Isolation: User from tenant_b searches for the same query -> MUST return 0 results
    cross_tenant_search = await async_client.post(
        "/api/v1/retrieval/search",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"query": "laptop disk encryption passwords", "top_n": 5},
    )
    assert cross_tenant_search.status_code == 200
    assert len(cross_tenant_search.json()["results"]) == 0

    # 8. Analyst searches for accessible document -> MUST retrieve cafeteria guide
    cafe_search = await async_client.post(
        "/api/v1/retrieval/search",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"query": "fresh sandwiches cafeteria", "top_n": 5},
    )
    assert cafe_search.status_code == 200
    cafe_results = cafe_search.json()["results"]
    assert len(cafe_results) > 0
    assert cafe_results[0]["source"]["filename"] == "cafe_guide.md"
