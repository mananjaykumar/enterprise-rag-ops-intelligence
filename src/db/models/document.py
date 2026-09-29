import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin


class DocumentLifecycleStatus(enum.StrEnum):
    """Lifecycle states of an ingested document."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"


class Document(Base, TimestampMixin):
    """Master document entity storing metadata, versioning, and access control."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_documents_tenant_active", "tenant_id", "is_active"),
        Index("idx_documents_hash", "tenant_id", "file_hash_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    parent_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="default_tenant",
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[DocumentLifecycleStatus] = mapped_column(
        Enum(DocumentLifecycleStatus, name="document_lifecycle_status_enum", native_enum=True),
        nullable=False,
        default=DocumentLifecycleStatus.PENDING,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=["admin", "manager", "analyst"],
    )
    # Using 'doc_metadata' attribute name to prevent collision with SQLAlchemy Base.metadata
    doc_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base):
    """Vectorized and tokenized document chunk with rich citation metadata."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("idx_chunks_retrieval_filter", "tenant_id", "is_active", "embedding_model"),
        Index("idx_chunks_fts", "fts_tokens", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Source & Citation Metadata
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    heading_hierarchy: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    chunk_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    table_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    char_start_idx: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end_idx: Mapped[int | None] = mapped_column(Integer, nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Hard Security Inheritance
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Model Lineage Segregation
    embedding_model: Mapped[str] = mapped_column(
        String(64), nullable=False, default="gemini-embedding-001"
    )
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False, default=768)

    # Dense Vector Column (768 dimensions)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)

    # Lexical Full-Text Search TSVECTOR (Generated column in PostgreSQL)
    fts_tokens: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
