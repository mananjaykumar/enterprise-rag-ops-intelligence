from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.db.session import engine
from src.main import app


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_connections():
    """Guarantees connection pool is disposed before the test's event loop closes."""
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provides an asynchronous HTTP test client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
