import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_and_rbac_flow(async_client: AsyncClient):
    """Verifies user registration, login, token authentication, and RBAC 403 rejection."""
    # Use unique email per test run
    random_suffix = uuid.uuid4().hex[:6]
    analyst_email = f"analyst_{random_suffix}@enterprise.com"
    admin_email = f"admin_{random_suffix}@enterprise.com"
    password = "SecurePassword123!"

    # 1. Register an Analyst User
    reg_response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": analyst_email,
            "password": password,
            "full_name": "Test Analyst",
            "role": "analyst",
            "tenant_id": "test_tenant",
        },
    )
    assert reg_response.status_code == 201
    analyst_data = reg_response.json()
    assert analyst_data["email"] == analyst_email
    assert analyst_data["role"] == "analyst"
    assert "hashed_password" not in analyst_data

    # 2. Test Duplicate Registration (Should return 409 Conflict)
    dup_response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": analyst_email,
            "password": password,
            "full_name": "Duplicate Analyst",
            "role": "analyst",
            "tenant_id": "test_tenant",
        },
    )
    assert dup_response.status_code == 409

    # 3. Test Login with Incorrect Password (Should return 401 Unauthorized)
    bad_login = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": analyst_email,
            "password": "WrongPassword!",
            "tenant_id": "test_tenant",
        },
    )
    assert bad_login.status_code == 401

    # 4. Login with Correct Password -> Get JWT
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": analyst_email,
            "password": password,
            "tenant_id": "test_tenant",
        },
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    analyst_token = token_data["access_token"]
    assert token_data["token_type"] == "bearer"

    # 5. Access /me with Bearer Token
    me_response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == analyst_email

    # 6. Test RBAC: Analyst attempting Admin endpoint -> MUST be 403 Forbidden!
    forbidden_response = await async_client.get(
        "/api/v1/auth/admin-only",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert forbidden_response.status_code == 403
    assert "Operation forbidden" in forbidden_response.json()["detail"]

    # 7. Register and Login an Admin User
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": admin_email,
            "password": password,
            "full_name": "Test Admin",
            "role": "admin",
            "tenant_id": "test_tenant",
        },
    )
    admin_login = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": admin_email,
            "password": password,
            "tenant_id": "test_tenant",
        },
    )
    admin_token = admin_login.json()["access_token"]

    # 8. Test RBAC: Admin accessing Admin endpoint -> MUST be 200 OK!
    admin_access = await async_client.get(
        "/api/v1/auth/admin-only",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_access.status_code == 200
    assert "Access granted" in admin_access.json()["message"]
