import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models.document import Document, DocumentChunk, DocumentLifecycleStatus
from src.db.session import AsyncSessionLocal
from src.domain.interfaces.embedding import BaseEmbeddingClient
from src.domain.interfaces.storage import BaseStorageClient
from src.infrastructure.ai.gemini import GeminiEmbeddingClient
from src.infrastructure.storage.local import LocalStorageClient
from src.services.parser import DocumentParser

logger = logging.getLogger("enterprise_rag.ingestion")


class IngestionService:
    """Orchestrates parsing, embedding, and atomic document version superseding."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        storage_client: BaseStorageClient | None = None,
        embedding_client: BaseEmbeddingClient | None = None,
        parser: DocumentParser | None = None,
    ) -> None:
        self.session_factory = session_factory or AsyncSessionLocal
        self.storage = storage_client or LocalStorageClient()
        self.embedder = embedding_client or GeminiEmbeddingClient()
        self.parser = parser or DocumentParser()

    async def process_document(self, document_id: str) -> int:
        """Processes an enqueued document end-to-end. Returns total chunks indexed."""
        doc_uuid = uuid.UUID(document_id)

        async with self.session_factory() as session:
            # 1. Fetch document and update status to PROCESSING
            stmt = select(Document).where(Document.id == doc_uuid)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if doc is None:
                raise ValueError(f"Document with ID {document_id} not found.")

            doc.status = DocumentLifecycleStatus.PROCESSING
            await session.commit()

        try:
            # 2. Parse file into structural Markdown AST blocks
            parsed_blocks = self.parser.parse_file(doc.storage_path, doc.mime_type)
            if not parsed_blocks:
                raise ValueError(f"No parseable content extracted from file: {doc.filename}")

            logger.info(
                "Extracted %d structural blocks from '%s'", len(parsed_blocks), doc.filename
            )

            # 3. Batch generate vector embeddings (768 dimensions)
            contents = [block.content for block in parsed_blocks]
            embeddings = await self.embedder.embed_documents(contents)

            # 4. Atomic Database Activation Transaction
            async with self.session_factory() as session:
                # Re-fetch document inside activation transaction
                doc_stmt = select(Document).where(Document.id == doc_uuid)
                doc_res = await session.execute(doc_stmt)
                active_doc = doc_res.scalar_one()

                # Step A: Supersede previous active versions of this document in the same tenant
                supersede_stmt = (
                    update(Document)
                    .where(
                        Document.tenant_id == active_doc.tenant_id,
                        Document.filename == active_doc.filename,
                        Document.id != active_doc.id,
                        Document.is_active == True,  # noqa: E712
                    )
                    .values(
                        status=DocumentLifecycleStatus.SUPERSEDED,
                        is_active=False,
                    )
                )
                await session.execute(supersede_stmt)

                # Step B: Deactivate chunks of superseded documents
                deactivate_chunks = (
                    update(DocumentChunk)
                    .where(
                        DocumentChunk.tenant_id == active_doc.tenant_id,
                        DocumentChunk.document_id != active_doc.id,
                        DocumentChunk.is_active == True,  # noqa: E712
                    )
                    .values(is_active=False)
                )
                await session.execute(deactivate_chunks)

                # Step C: Insert new chunks inheriting permissions from parent document
                chunks_to_insert = []
                for idx, (block, emb) in enumerate(zip(parsed_blocks, embeddings, strict=True)):
                    chunk = DocumentChunk(
                        document_id=active_doc.id,
                        tenant_id=active_doc.tenant_id,
                        chunk_index=idx,
                        page_number=block.page_number,
                        section_heading=block.section_heading,
                        heading_hierarchy=block.heading_hierarchy,
                        chunk_type=block.chunk_type,
                        table_metadata=block.table_metadata,
                        char_start_idx=block.char_start_idx,
                        char_end_idx=block.char_end_idx,
                        content=block.content,
                        content_hash=block.content_hash,
                        # Hard Security Inheritance (ADR-008)
                        allowed_roles=active_doc.allowed_roles,
                        is_active=True,
                        embedding_model=self.embedder.model_name,
                        embedding_dimension=self.embedder.dimension,
                        embedding=emb,
                    )
                    chunks_to_insert.append(chunk)

                session.add_all(chunks_to_insert)

                # Step D: Mark current document as ACTIVE
                active_doc.status = DocumentLifecycleStatus.ACTIVE
                active_doc.is_active = True
                await session.commit()

            logger.info(
                "Successfully indexed %d chunks for '%s'", len(chunks_to_insert), doc.filename
            )
            return len(chunks_to_insert)

        except Exception as exc:
            logger.error("Failed to ingest document '%s': %s", doc.filename, exc)
            async with self.session_factory() as session:
                fail_stmt = (
                    update(Document)
                    .where(Document.id == doc_uuid)
                    .values(
                        status=DocumentLifecycleStatus.FAILED,
                        error_log=str(exc),
                    )
                )
                await session.execute(fail_stmt)
                await session.commit()
            raise exc
