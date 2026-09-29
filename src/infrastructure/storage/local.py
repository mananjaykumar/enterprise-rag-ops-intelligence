import os
from pathlib import Path
from typing import BinaryIO

from src.core.config import get_settings
from src.domain.interfaces.storage import BaseStorageClient

settings = get_settings()


class LocalStorageClient(BaseStorageClient):
    """Local filesystem storage adapter implementing BaseStorageClient."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, destination_path: str, data: BinaryIO | bytes) -> str:
        """Persists file bytes to local disk safely preventing directory traversal."""
        # Sanitize destination path
        clean_relative_path = Path(destination_path).as_posix().lstrip("/")
        target_path = (self.base_dir / clean_relative_path).resolve()

        # Prevent directory traversal attacks (e.g., ../../etc/passwd)
        if not str(target_path).startswith(str(self.base_dir.resolve())):
            raise ValueError(f"Illegal file path outside storage directory: {destination_path}")

        target_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            target_path.write_bytes(data)
        else:
            with open(target_path, "wb") as f:
                f.write(data.read())

        return str(target_path)

    async def read_file(self, file_path: str) -> bytes:
        """Reads raw file bytes from disk."""
        target_path = Path(file_path).resolve()
        if not target_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return target_path.read_bytes()

    async def delete_file(self, file_path: str) -> bool:
        """Removes a file from disk if it exists."""
        target_path = Path(file_path).resolve()
        if target_path.exists():
            os.remove(target_path)
            return True
        return False
