import uuid
from datetime import UTC, datetime, timedelta
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
            try:
                stmt = select(IngestionJob).where(IngestionJob.id == job_id)
                res = await session.execute(stmt)
                job = res.scalar_one_or_none()

                if not job:
                    return

                # Check if we can retry or if it is a permanent failure
                if job.attempts < job.max_attempts:
                    # RETRY STATE: Put it back in the queue, clear locks, increment attempts
                    job.status = JobStatus.QUEUED
                    job.locked_by = None
                    job.locked_at = None
                    job.error_message = f"Attempt {job.attempts} failed: {error_message}"

                    # Optional: Sync master document back to PENDING so worker can process again
                    if job.document_id:
                        doc_stmt = (
                            update(Document)
                            .where(Document.id == job.document_id)
                            .values(status=DocumentLifecycleStatus.PENDING)
                        )
                        await session.execute(doc_stmt)
                else:
                    # PERMANENT FAILURE: Hard stop after max attempts exhausted
                    job.status = JobStatus.FAILED
                    job.error_message = f"Max retries exhausted. Final Error: {error_message}"
                
                if job.document_id:
                        doc_stmt = (
                            update(Document)
                            .where(Document.id == job.document_id)
                            .values(
                                status=DocumentLifecycleStatus.FAILED,
                                error_log=f"Job execution permanently failed after {job.max_attempts} retries."
                            )
                        )
                        await session.execute(doc_stmt)
                        
                await session.commit()
                
            #     stmt = (
            #     update(IngestionJob)
            #     .where(IngestionJob.id == uuid.UUID(job_id))
            #     .values(
            #         status=JobStatus.FAILED,
            #         error_message=error_message,
            #         locked_at=None,
            #     )
            # )
            # await session.execute(stmt)
            # await session.commit()
            except Exception as e:
                await session.rollback()
                raise e

    async def clear_orphaned_jobs(self, timeout_minutes: int = 60) -> int:
        """
        Identifies tasks stuck in PROCESSING state longer than the timeout threshold
        and safely releases their distributed locks back into the QUEUED state.
        """
        threshold_time = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
        
        async with self.session_factory() as session:
            try:
                stmt = (
                    update(IngestionJob)
                    .where(
                        IngestionJob.status == JobStatus.PROCESSING,
                        IngestionJob.locked_at < threshold_time
                    )
                    .values(
                        status=JobStatus.QUEUED,
                        locked_by=None,
                        locked_at=None
                    )
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount  # Returns the total number of rescued records
            except Exception as e:
                await session.rollback()
                raise e
