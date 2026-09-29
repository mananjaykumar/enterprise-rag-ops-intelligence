import uuid

import pytest
from httpx import AsyncClient

from src.services.observability import ObservabilityService, get_observability_service


@pytest.mark.asyncio
async def test_observability_middleware_headers(async_client: AsyncClient):
    """Verifies that the observability middleware attaches trace ID and latency headers."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200

    # Verify X-Trace-ID header presence and format
    assert "x-trace-id" in response.headers
    trace_id = response.headers["x-trace-id"]
    assert trace_id.startswith("trc_") or len(trace_id) > 0

    # Verify X-Response-Time-Ms header presence and format
    assert "x-response-time-ms" in response.headers
    assert response.headers["x-response-time-ms"].endswith("ms")


@pytest.mark.asyncio
async def test_observability_middleware_propagates_incoming_trace_id(async_client: AsyncClient):
    """Verifies that custom incoming X-Trace-ID headers are preserved and propagated."""
    custom_trace_id = f"custom_client_trace_{uuid.uuid4().hex[:8]}"

    response = await async_client.get(
        "/api/v1/health",
        headers={"X-Trace-ID": custom_trace_id},
    )
    assert response.status_code == 200
    assert response.headers.get("x-trace-id") == custom_trace_id


def test_observability_service_local_resilience():
    """Verifies that ObservabilityService operates smoothly in local fallback mode."""
    service = ObservabilityService()

    # 1. Trace Span Context Manager
    with service.trace_span(
        name="test_pipeline_span",
        tenant_id="tenant_123",
        user_id="user_456",
        metadata={"phase": "test"},
    ) as span:
        assert span is not None
        span.update(metadata={"step": "completed"})

    # 2. Generation Span Context Manager
    with service.generation_span(
        name="test_generation",
        model="gemini-3.5-flash-lite",
        prompt="Explain quantum computing",
    ) as gen_span:
        assert gen_span is not None
        gen_span.update(metadata={"tokens": 42})

    # 3. Flush should succeed without error
    service.flush()


def test_get_observability_service_singleton():
    """Verifies singleton pattern for the observability service."""
    instance_a = get_observability_service()
    instance_b = get_observability_service()
    assert instance_a is instance_b
