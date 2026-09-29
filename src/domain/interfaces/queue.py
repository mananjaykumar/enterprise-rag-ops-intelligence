from abc import ABC, abstractmethod
from typing import Any


class BaseJobQueueClient(ABC):
    """Abstract interface for asynchronous job enqueueing and processing."""

    @abstractmethod
    async def enqueue(
        self,
        task_type: str,
        payload: dict[str, Any],
        tenant_id: str = "default_tenant",
        document_id: str | None = None,
    ) -> str:
        """Enqueue a background task and return the job ID."""
        pass

    @abstractmethod
    async def fetch_next_job(self) -> dict[str, Any] | None:
        """Fetch and lock the next pending job in the queue."""
        pass

    @abstractmethod
    async def complete_job(self, job_id: str) -> None:
        """Mark a job as successfully completed."""
        pass

    @abstractmethod
    async def fail_job(self, job_id: str, error_message: str) -> None:
        """Mark a job as failed with an error message."""
        pass
