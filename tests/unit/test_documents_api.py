import io
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_document_api_flow(async_client: AsyncClient):
    """Tests document upload RBAC, validation, queuing, and tenant isolation."""
    random_id = uuid.uuid4().hex[:6]
    analyst_email = f"analyst_doc_{random_id}@corp.com"
    manager_email = f"manager_doc_{random_id}@corp.com"
    other_tenant_email = f"other_doc_{random_id}@othercorp.com"
    password = "SecurePassword123!"

    # 1. Register test accounts
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": analyst_email,
            "password": password,
            "full_name": "Doc Analyst",
            "role": "analyst",
            "tenant_id": "tenant_alpha",
        },
    )
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": manager_email,
            "password": password,
            "full_name": "Doc Manager",
            "role": "manager",
            "tenant_id": "tenant_alpha",
        },
    )
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": other_tenant_email,
            "password": password,
            "full_name": "Other Tenant User",
            "role": "manager",
            "tenant_id": "tenant_beta",
        },
    )

    # 2. Acquire JWT tokens
    analyst_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": analyst_email, "password": password, "tenant_id": "tenant_alpha"},
    )
    analyst_token = analyst_login.json()["access_token"]

    manager_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": manager_email, "password": password, "tenant_id": "tenant_alpha"},
    )
    manager_token = manager_login.json()["access_token"]

    other_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": other_tenant_email, "password": password, "tenant_id": "tenant_beta"},
    )
    other_token = other_login.json()["access_token"]

    # 3. Unauthenticated upload -> 401 Unauthorized
    dummy_file = io.BytesIO(b"# Security Policy\nAll passwords must have 12 chars.")
    unauth_resp = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.md", dummy_file, "text/markdown")},
    )
    assert unauth_resp.status_code == 401

    # 4. RBAC: Analyst cannot upload -> 403 Forbidden
    dummy_file.seek(0)
    analyst_resp = await async_client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {analyst_token}"},
        files={"file": ("policy.md", dummy_file, "text/markdown")},
    )
    assert analyst_resp.status_code == 403

    # 5. Invalid File Type -> 400 Bad Request
    unsupported_file = io.BytesIO(b"echo 'malicious'")
    bad_type_resp = await async_client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {manager_token}"},
        files={"file": ("script.sh", unsupported_file, "application/x-sh")},
    )
    assert bad_type_resp.status_code == 400
    assert "Unsupported file type" in bad_type_resp.json()["detail"]

    # 6. Manager uploads valid document -> 202 Accepted
    dummy_file.seek(0)
    upload_resp = await async_client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {manager_token}"},
        data={"title": "Corporate IT Security Policy", "allowed_roles": "admin,manager"},
        files={"file": ("it_policy.md", dummy_file, "text/markdown")},
    )
    assert upload_resp.status_code == 202
    upload_data = upload_resp.json()
    assert upload_data["status"] == "PENDING"
    assert "document_id" in upload_data
    assert "job_id" in upload_data
    doc_id = upload_data["document_id"]

    # 7. Query document status -> 200 OK
    status_resp = await async_client.get(
        f"/api/v1/documents/{doc_id}/status",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["id"] == doc_id
    assert status_data["filename"] == "it_policy.md"
    assert status_data["status"] == "PENDING"
    assert status_data["is_active"] is False
    assert status_data["chunk_count"] == 0

    # 8. Cross-tenant isolation -> 404 Not Found (User in tenant_beta cannot see tenant_alpha doc)
    cross_tenant_resp = await async_client.get(
        f"/api/v1/documents/{doc_id}/status",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert cross_tenant_resp.status_code == 404
