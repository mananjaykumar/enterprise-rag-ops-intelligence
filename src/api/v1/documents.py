import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies import get_current_user, require_roles
from src.core.config import get_settings
from src.db.models.document import Document, DocumentChunk, DocumentLifecycleStatus
from src.db.models.job import IngestionJob, JobStatus
from src.db.models.user import User, UserRole
from src.db.session import get_db
from src.infrastructure.storage.local import LocalStorageClient
from src.schemas.document import DocumentListItem, DocumentStatusResponse, DocumentUploadResponse

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
settings = get_settings()
storage_client = LocalStorageClient(base_dir=settings.UPLOAD_DIR)


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentUploadResponse,
)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[
        User,
        Depends(require_roles([UserRole.ADMIN, UserRole.MANAGER])),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    title: Annotated[str | None, Form()] = None,
    allowed_roles: Annotated[str, Form()] = "admin,manager,analyst",
) -> DocumentUploadResponse:
    # 1. Validate file extension
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # 2. Read bytes & compute SHA-256
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # 3. Store file to storage backend
    saved_path = await storage_client.save_file(
        destination_path=f"{current_user.tenant_id}/{filename}",
        data=file_bytes,
    )

    # Parse allowed_roles comma-separated string
    roles_list = [r.strip() for r in allowed_roles.split(",") if r.strip()]

    # 4. Atomic DB insert: Document + IngestionJob
    document = Document(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        title=title or filename,
        filename=filename,
        storage_path=saved_path,
        file_hash_sha256=file_hash,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(file_bytes),
        version=1,
        status=DocumentLifecycleStatus.PENDING,
        is_active=False,
        allowed_roles=roles_list,
        doc_metadata={},
    )
    db.add(document)

    job = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        document_id=document.id,
        task_type="PARSE_AND_INDEX",
        status=JobStatus.QUEUED,
        payload={"storage_path": saved_path, "filename": filename},
        attempts=0,
        max_attempts=3,
    )
    db.add(job)

    await db.commit()
    await db.refresh(document)
    await db.refresh(job)

    return DocumentUploadResponse(
        document_id=document.id,
        job_id=job.id,
        filename=document.filename,
        status=document.status,
        message="Document uploaded and queued for processing.",
    )


@router.get(
    "",
    response_model=list[DocumentListItem],
    summary="List all documents for the authenticated tenant",
)
async def list_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DocumentListItem]:
    """Returns all documents in the caller's tenant boundary with chunk counts."""
    # Subquery: chunk counts per document
    chunk_counts = (
        select(DocumentChunk.document_id, func.count(DocumentChunk.id).label("cnt"))
        .where(DocumentChunk.tenant_id == current_user.tenant_id)
        .group_by(DocumentChunk.document_id)
        .subquery()
    )

    stmt = (
        select(Document, func.coalesce(chunk_counts.c.cnt, 0).label("chunk_count"))
        .outerjoin(chunk_counts, Document.id == chunk_counts.c.document_id)
        .where(Document.tenant_id == current_user.tenant_id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for doc, chunk_count in rows:
        items.append(
            DocumentListItem(
                id=doc.id,
                filename=doc.filename,
                title=doc.title,
                mime_type=doc.mime_type,
                status=doc.status,
                is_active=doc.is_active,
                allowed_roles=doc.allowed_roles,
                chunk_count=chunk_count,
                created_at=doc.created_at,
            )
        )
    return items


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
)
async def get_document_status(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentStatusResponse:
    # 1. Fetch document with tenant isolation
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # 2. Enforce RBAC read permission
    if (
        current_user.role != UserRole.ADMIN
        and current_user.role.value not in document.allowed_roles
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: insufficient role permissions for this document.",
        )

    # 3. Query chunk count
    count_stmt = select(func.count(DocumentChunk.id)).where(
        DocumentChunk.document_id == document.id,
        DocumentChunk.tenant_id == current_user.tenant_id,
    )
    count_result = await db.execute(count_stmt)
    chunk_count = count_result.scalar() or 0

    return DocumentStatusResponse(
        id=document.id,
        filename=document.filename,
        title=document.title,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
        version=document.version,
        status=document.status,
        is_active=document.is_active,
        allowed_roles=document.allowed_roles,
        chunk_count=chunk_count,
        error_log=document.error_log,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )
