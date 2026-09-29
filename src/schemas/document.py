import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from src.db.models.document import DocumentLifecycleStatus


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    job_id: uuid.UUID
    filename: str
    status: DocumentLifecycleStatus
    message: str


class DocumentStatusResponse(BaseModel):
    id: uuid.UUID
    filename: str
    title: str | None
    mime_type: str
    size_bytes: int
    version: int
    status: DocumentLifecycleStatus
    is_active: bool
    allowed_roles: list[str]
    chunk_count: int
    error_log: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListItem(BaseModel):
    id: uuid.UUID
    filename: str
    title: str | None
    mime_type: str
    status: DocumentLifecycleStatus
    is_active: bool
    allowed_roles: list[str]
    chunk_count: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
