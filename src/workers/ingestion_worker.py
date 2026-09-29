import asyncio
import logging
from typing import Any

from src.infrastructure.queue.postgres import PostgresJobQueueClient
from src.services.ingestion import IngestionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enterprise_rag.worker")


class IngestionWorker:
    """Background worker continuously pulling tasks from PostgreSQL via SKIP LOCKED."""

    def __init__(
        self,
        queue_client: PostgresJobQueueClient | None = None,
        ingestion_service: IngestionService | None = None,
    ) -> None:
        self.queue = queue_client or PostgresJobQueueClient()
        self.ingestion = ingestion_service or IngestionService()
        self._running = False

    async def process_one_job(self) -> dict[str, Any] | None:
        """Pulls and executes a single job atomically. Returns job metadata or None."""
        job = await self.queue.fetch_next_job()
        if not job:
            return None

        job_id = job["id"]
        doc_id = job["document_id"]
        logger.info("Worker picked up job %s (Task: %s, Doc: %s)", job_id, job["task_type"], doc_id)

        try:
            if not doc_id:
                raise ValueError("Missing document_id in job payload.")

            # Process ingestion
            chunks_count = await self.ingestion.process_document(doc_id)

            # Mark job complete
            await self.queue.complete_job(job_id)
            logger.info("Job %s completed successfully (%d chunks indexed)", job_id, chunks_count)
            return job

        except Exception as exc:
            logger.error("Job %s failed: %s", job_id, exc)
            await self.queue.fail_job(job_id, error_message=str(exc))
            return job

    async def run(self, poll_interval_seconds: float = 2.0) -> None:
        """Starts continuous polling loop."""
        self._running = True
        logger.info("Ingestion Worker started. Polling queue every %.1fs...", poll_interval_seconds)

        while self._running:
            try:
                job = await self.process_one_job()
                # If no job was ready, sleep before polling again
                if not job:
                    await asyncio.sleep(poll_interval_seconds)
            except Exception as exc:
                logger.warning("Transient error in worker polling loop: %s. Retrying in 5s...", exc)
                await asyncio.sleep(5.0)

    def stop(self) -> None:
        """Stops the worker loop."""
        self._running = False
        logger.info("Ingestion Worker stopping...")


if __name__ == "__main__":
    worker = IngestionWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        worker.stop()
