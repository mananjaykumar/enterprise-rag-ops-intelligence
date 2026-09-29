from abc import ABC, abstractmethod
from typing import BinaryIO


class BaseStorageClient(ABC):
    """Abstract interface for file and object storage operations."""

    @abstractmethod
    async def save_file(self, destination_path: str, data: BinaryIO | bytes) -> str:
        """Persist raw file data and return its storage URI."""
        pass

    @abstractmethod
    async def read_file(self, file_path: str) -> bytes:
        """Read and return raw file bytes from storage."""
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Remove file from storage."""
        pass
