import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.api.middleware.observability import ObservabilityMiddleware
from src.api.v1.agent import router as agent_router
from src.api.v1.auth import router as auth_router
from src.api.v1.documents import router as documents_router
from src.api.v1.health import router as health_router
from src.api.v1.rag import router as rag_router
from src.api.v1.retrieval import router as retrieval_router
from src.api.v1.sql import router as sql_router
from src.core.config import get_settings
from src.db.base import Base
from src.db.session import AsyncSessionLocal, engine
from src.services.observability import get_observability_service
from src.workers.ingestion_worker import IngestionWorker
from src.infrastructure.queue.postgres import PostgresJobQueueClient 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enterprise_rag")

settings = get_settings()

sweeper_task: asyncio.Task | None = None

async def start_orphaned_jobs_sweeper(queue_client: PostgresJobQueueClient, interval_seconds: int = 300) -> None:
    """Autonomous background loop that unlocks zombie processing tasks periodically."""
    while True:
        try:
            logger.info("Running periodic background check for orphaned processing tasks...")
            rescued_count = await queue_client.clear_orphaned_jobs(timeout_minutes=60)
            if rescued_count > 0:
                logger.warning("Successfully rescued %d zombie tasks back into the active queue pipeline.", rescued_count)
        except Exception as err:
            logger.error("Orphaned job cleaner loop encountered an unexpected failure: %s", err)
        
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Executes startup checks before accepting traffic and cleans up resources on shutdown.
    """
    global sweeper_task
    logger.info("Initializing %s...", settings.PROJECT_NAME)

    # 1. Startup Database Connectivity & pgvector Verification
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1;"))
            logger.info("Database connection pool established (ping=%s)", result.scalar() == 1)

            # 2. Ensure pgvector extension and tables exist
            async with engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database schemas, pgvector extension, and tables verified/created.")

        # 3. Automatic Seeding for Free Hosting Platforms (e.g. Render Free where Web Shell is disabled)
        if os.getenv("AUTO_SEED", "false").lower() == "true":
            try:
                from scripts.seed_operational_data import seed_admin_user, seed_operational_entities
                async with AsyncSessionLocal() as session:
                    await seed_admin_user(session)
                    counts = await seed_operational_entities(session)
                    await session.commit()
                    logger.info("Automatic database seeding completed on startup: %s", counts)
            except Exception as seed_err:
                logger.warning("Automatic startup seeding encountered an issue: %s", seed_err)

    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
        raise exc

    # 4. Start embedded ingestion worker in background (enables 100% free single-container deployments)
    worker = None
    worker_task = None
    queue_client = PostgresJobQueueClient()
    try:
        # Initializing the autonomous sweeper loop task reference
        sweeper_task = asyncio.create_task(start_orphaned_jobs_sweeper(queue_client, interval_seconds=300))
        logger.info("Autonomous Self-Healing Orphaned Jobs Sweeper loop initialized.")

        worker = IngestionWorker()
        worker_task = asyncio.create_task(worker.run())
        logger.info("Embedded Ingestion Worker background task started.")
    except Exception as exc:
        logger.warning("Could not launch embedded ingestion worker: %s", exc)

    yield  # Application accepts incoming HTTP requests

    # 4. Graceful Shutdown
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    if sweeper_task:
        sweeper_task.cancel()
        logger.info("Background sweeper task loop terminated.")
    if worker:
        worker.stop()
    if worker_task:
        worker_task.cancel()
    get_observability_service().flush()
    await engine.dispose()
    logger.info("Database connection pool closed.")


def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="Dual-Intelligence Enterprise Knowledge & Operations Platform",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Enterprise Observability & Tracing Middleware
    app.add_middleware(ObservabilityMiddleware)

    # Root health probe for container orchestrators (Docker, ALB, K8s)
    @app.get("/health", tags=["Health & Readiness"], include_in_schema=False)
    async def root_health() -> dict[str, str]:
        return {"status": "healthy"}

    # HTTP Trigger for Database Seeding (Ideal for Serverless / Free Tier where Shell is disabled)
    @app.post("/api/v1/admin/seed", tags=["Administration"])
    async def trigger_database_seed() -> dict[str, Any]:
        """Seeds or resets operational demo database records."""
        try:
            from scripts.seed_operational_data import (
                clear_operational_data,
                seed_admin_user,
                seed_operational_entities,
            )
            async with AsyncSessionLocal() as session:
                await seed_admin_user(session)
                await clear_operational_data(session)
                counts = await seed_operational_entities(session)
                await session.commit()
            return {
                "status": "success",
                "message": "Operational database seeded successfully",
                "counts": counts,
            }
        except Exception as e:
            logger.error("Seeding endpoint failed: %s", e)
            return {"status": "error", "message": str(e)}

    # Register API Routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(retrieval_router, prefix="/api/v1")
    app.include_router(rag_router, prefix="/api/v1")
    app.include_router(sql_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")

    return app


app = create_application()
