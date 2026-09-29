import hashlib
import json
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
async def test_grounded_rag_and_citation_lineage(async_client: AsyncClient):
    """Tests grounded Q&A, bracket citation matching, hallucination refusal, and SSE streaming."""
    random_id = uuid.uuid4().hex[:6]
    tenant = f"tenant_rag_{random_id}"

    manager_email = f"manager_rag_{random_id}@corp.com"
    analyst_email = f"analyst_rag_{random_id}@corp.com"
    password = "SecurePassword123!"

    # 1. Register accounts
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": manager_email,
            "password": password,
            "full_name": "RAG Manager",
            "role": "manager",
            "tenant_id": tenant,
        },
    )
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": analyst_email,
            "password": password,
            "full_name": "RAG Analyst",
            "role": "analyst",
            "tenant_id": tenant,
        },
    )

    # 2. Acquire JWT tokens
    mgr_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": manager_email, "password": password, "tenant_id": tenant},
    )
    mgr_token = mgr_resp.json()["access_token"]

    ana_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": analyst_email, "password": password, "tenant_id": tenant},
    )
    ana_token = ana_resp.json()["access_token"]

    # 3. Seed active documents & chunks with live Gemini embeddings
    embedding_client = GeminiEmbeddingClient()
    equip_text = "All company laptops must have full disk encryption enabled and passwords must be at least 16 characters long."
    visitor_text = (
        "All visitors must register at the reception desk and wear a visitor badge at all times."
    )

    equip_vec = await embedding_client.embed_query(equip_text)
    visitor_vec = await embedding_client.embed_query(visitor_text)

    async with AsyncSession(engine) as session:
        # Document 1: Restricted Equipment Policy (Admin & Manager only)
        doc_equip = Document(
            id=uuid.uuid4(),
            tenant_id=tenant,
            title="Company Equipment Policy",
            filename="equipment_policy.md",
            storage_path="/data/dummy/equipment_policy.md",
            file_hash_sha256="hash_equip",
            mime_type="text/markdown",
            size_bytes=len(equip_text),
            version=1,
            status=DocumentLifecycleStatus.ACTIVE,
            is_active=True,
            allowed_roles=["admin", "manager"],
            doc_metadata={},
        )
        session.add(doc_equip)

        chunk_equip = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_equip.id,
            tenant_id=tenant,
            chunk_index=0,
            content=equip_text,
            content_hash=hashlib.sha256(equip_text.encode()).hexdigest(),
            allowed_roles=["admin", "manager"],
            is_active=True,
            embedding_model=settings.ACTIVE_EMBEDDING_MODEL,
            embedding_dimension=768,
            embedding=equip_vec,
            heading_hierarchy=["Hardware", "Laptops"],
            section_heading="Laptop Security",
            chunk_type="text",
            table_metadata={},
        )
        session.add(chunk_equip)

        # Document 2: Visitor Policy (All roles: Admin, Manager, Analyst)
        doc_visitor = Document(
            id=uuid.uuid4(),
            tenant_id=tenant,
            title="Office Visitor Policy",
            filename="visitor_policy.md",
            storage_path="/data/dummy/visitor_policy.md",
            file_hash_sha256="hash_visitor",
            mime_type="text/markdown",
            size_bytes=len(visitor_text),
            version=1,
            status=DocumentLifecycleStatus.ACTIVE,
            is_active=True,
            allowed_roles=["admin", "manager", "analyst"],
            doc_metadata={},
        )
        session.add(doc_visitor)

        chunk_visitor = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_visitor.id,
            tenant_id=tenant,
            chunk_index=0,
            content=visitor_text,
            content_hash=hashlib.sha256(visitor_text.encode()).hexdigest(),
            allowed_roles=["admin", "manager", "analyst"],
            is_active=True,
            embedding_model=settings.ACTIVE_EMBEDDING_MODEL,
            embedding_dimension=768,
            embedding=visitor_vec,
            heading_hierarchy=["Office Guidelines"],
            section_heading="Badge Requirements",
            chunk_type="text",
            table_metadata={},
        )
        session.add(chunk_visitor)

        await session.commit()

    # 4. Unauthenticated request -> 401 Unauthorized
    unauth_resp = await async_client.post(
        "/api/v1/rag/ask",
        json={"question": "What are the laptop security requirements?"},
    )
    assert unauth_resp.status_code == 401

    # 5. Manager asks grounded question -> 200 OK with citations
    mgr_ask_resp = await async_client.post(
        "/api/v1/rag/ask",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"question": "What are the password length requirements for company laptops?"},
    )
    assert mgr_ask_resp.status_code == 200
    mgr_data = mgr_ask_resp.json()
    assert mgr_data["has_sufficient_context"] is True
    assert "16" in mgr_data["answer"]
    assert len(mgr_data["citations"]) > 0
    assert mgr_data["citations"][0]["filename"] == "equipment_policy.md"
    assert mgr_data["citations"][0]["section_heading"] == "Laptop Security"

    # 6. Zero-hallucination refusal on out-of-context query
    cookie_resp = await async_client.post(
        "/api/v1/rag/ask",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"question": "How do I bake chocolate chip cookies?"},
    )
    assert cookie_resp.status_code == 200
    cookie_data = cookie_resp.json()
    assert cookie_data["has_sufficient_context"] is False
    assert "not have sufficient information" in cookie_data["answer"].lower()
    assert len(cookie_data["citations"]) == 0

    # 7. RBAC security guardrail: Analyst asks for restricted equipment policy
    # Pre-retrieval filters block the chunk, causing RAG to refuse to answer
    ana_ask_resp = await async_client.post(
        "/api/v1/rag/ask",
        headers={"Authorization": f"Bearer {ana_token}"},
        json={"question": "What are the password length requirements for company laptops?"},
    )
    assert ana_ask_resp.status_code == 200
    ana_data = ana_ask_resp.json()
    assert ana_data["has_sufficient_context"] is False
    assert "not have sufficient information" in ana_data["answer"].lower()

    # 8. Server-Sent Events (SSE) streaming endpoint
    async with async_client.stream(
        "POST",
        "/api/v1/rag/stream",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"question": "What are the visitor badge requirements?"},
    ) as stream_resp:
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers["content-type"]

        events = []
        async for line in stream_resp.aiter_lines():
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                events.append(payload)

        # Must have token events and a terminal 'done' event with citations
        assert len(events) >= 2
        done_event = events[-1]
        assert done_event.get("event") == "done"
        assert done_event.get("has_sufficient_context") is True
        assert len(done_event.get("citations", [])) > 0
        assert done_event["citations"][0]["filename"] == "visitor_policy.md"
