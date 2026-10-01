import logging
import uuid
import asyncio

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from google.api_core.exceptions import ResourceExhausted


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

    async def _embed_with_micro_batches(self, contents: list[str], max_retries: int = 5) -> list[list[float]]:
        """
        Splits data into micro-batches and injects dynamic cool-down delays to
        bypass Google Gemini's Free Tier RPM and IP-based rate restrictions safely.
        """
        all_embeddings = []
        batch_size = 5  # 🟢 Safe size boundary: Sends only 5 Paragraphs at a time
        
        # Divide all chunks into sub-lists of 5 each
        micro_batches = [contents[i:i + batch_size] for i in range(0, len(contents), batch_size)]
        logger.info("Total content split into %d micro-batches to throttle API ingestion rate.", len(micro_batches))

        for idx, batch in enumerate(micro_batches):
            delay = 3  # Initial exponential wait threshold
            success = False
            
            for attempt in range(1, max_retries + 1):
                try:
                    # Current sub-batch call execution
                    batch_res = await self.embedder.embed_documents(batch)
                    all_embeddings.extend(batch_res)
                    success = True
                    break  # Success! Loop break karke agle batch par jao
                except ResourceExhausted as exc:
                    if attempt == max_retries:
                        logger.error("❌ Google Gemini quota bounds breached permanently after all backoff retries.")
                        raise exc
                    logger.warning(
                        "⚠️ Gemini Rate Limit Triggered at Micro-Batch %d/%d. Cooling down for %ss...",
                        idx + 1, len(micro_batches), delay
                    )
                    await asyncio.sleep(delay)
                    delay *= 2  # Doubles the wait window (3s -> 6s -> 12s)
            
            if not success:
                raise RuntimeError("Document embedding pipeline forcefully aborted due to constant rate exhaustion.")

            # 🟢 THE HACK GAP: 3-second pause after every safety chunk operation
            # so that Google's free counter resets
            if idx < len(micro_batches) - 1:
                logger.info("Micro-Batch %d/%d indexed. Pausing pipeline execution for 3 seconds...", idx + 1, len(micro_batches))
                await asyncio.sleep(3.0)

        return all_embeddings


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
            parsed_blocks = await asyncio.to_thread(
                self.parser.parse_file,
                doc.storage_path,
                doc.mime_type
            )
            if not parsed_blocks:
                raise ValueError(f"No parseable content extracted from file: {doc.filename}")

            logger.info(
                "Extracted %d structural blocks from '%s'", len(parsed_blocks), doc.filename
            )

            # 3. Batch generate vector embeddings (768 dimensions)
            contents = [block.content for block in parsed_blocks]
            # embeddings = await self.embedder.embed_documents(contents)
            embeddings = await self._embed_with_micro_batches(contents)

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
