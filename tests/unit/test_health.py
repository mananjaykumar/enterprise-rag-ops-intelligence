import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    """Verify that the health check endpoint returns HTTP 200 and healthy DB status."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["active_embedding_model"] == "gemini-embedding-001"
    assert "project" in data
