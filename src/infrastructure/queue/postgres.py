import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models.job import IngestionJob, JobStatus
from src.db.session import AsyncSessionLocal
from src.domain.interfaces.queue import BaseJobQueueClient


class PostgresJobQueueClient(BaseJobQueueClient):
    """PostgreSQL-native queue adapter implementing BaseJobQueueClient via SKIP LOCKED."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.session_factory = session_factory or AsyncSessionLocal

    async def enqueue(
        self,
        task_type: str,
        payload: dict[str, Any],
        tenant_id: str = "default_tenant",
        document_id: str | None = None,
    ) -> str:
        """Enqueues a new background task."""
        async with self.session_factory() as session:
            job = IngestionJob(
                task_type=task_type,
                payload=payload,
                tenant_id=tenant_id,
                document_id=uuid.UUID(document_id) if document_id else None,
                status=JobStatus.QUEUED,
            )
            session.add(job)
            await session.commit()
            return str(job.id)

    async def fetch_next_job(self) -> dict[str, Any] | None:
        """Fetches and locks the next queued job using FOR UPDATE SKIP LOCKED."""
        async with self.session_factory() as session:
            stmt = (
                select(IngestionJob)
                .where(IngestionJob.status == JobStatus.QUEUED)
                .order_by(IngestionJob.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if job is None:
                return None

            # Mark as processing and record lock timestamp
            job.status = JobStatus.PROCESSING
            job.attempts += 1
            job.locked_at = datetime.now(UTC)
            await session.commit()

            return {
                "id": str(job.id),
                "task_type": job.task_type,
                "payload": job.payload,
                "tenant_id": job.tenant_id,
                "document_id": str(job.document_id) if job.document_id else None,
                "attempts": job.attempts,
            }

    async def complete_job(self, job_id: str) -> None:
        """Marks a job as successfully completed."""
        async with self.session_factory() as session:
            stmt = (
                update(IngestionJob)
                .where(IngestionJob.id == uuid.UUID(job_id))
                .values(
                    status=JobStatus.COMPLETED,
                    locked_at=None,
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def fail_job(self, job_id: str, error_message: str) -> None:
        """Marks a job as failed with an error reason."""
        async with self.session_factory() as session:
            stmt = (
                update(IngestionJob)
                .where(IngestionJob.id == uuid.UUID(job_id))
                .values(
                    status=JobStatus.FAILED,
                    error_message=error_message,
                    locked_at=None,
                )
            )
            await session.execute(stmt)
            await session.commit()
