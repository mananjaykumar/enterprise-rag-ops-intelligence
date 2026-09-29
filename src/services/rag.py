import json
import logging
import re
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.db.models.user import User
from src.domain.interfaces.llm import BaseLLMClient
from src.infrastructure.ai.gemini_llm import GeminiLLMClient
from src.schemas.rag import CitationItem, RAGQueryRequest, RAGQueryResponse
from src.schemas.retrieval import RetrievedChunk
from src.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_INSTRUCTION = """You are an accurate, enterprise intelligence assistant.
Your answers MUST be strictly grounded in the provided numbered sources.

RULES:
1. Answer the question using ONLY the provided sources. Do not speculate or use outside knowledge.
2. Every factual statement or assertion MUST cite the source index in square brackets, e.g. [1] or [2].
3. Multiple sources can be cited together, e.g. [1][2].
4. If the provided sources DO NOT contain sufficient information to answer the question, state:
   "I do not have sufficient information in the provided documentation to answer this question."
5. Never invent or guess facts, dates, numbers, or rules not present in the sources.
"""

INSUFFICIENT_INFO_PHRASE = "do not have sufficient information"


class RAGService:
    """Grounded Generative Question-Answering Service with strict citation lineage."""

    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        llm_client: BaseLLMClient | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service or RetrievalService()
        self.llm_client = llm_client or GeminiLLMClient()

    def _build_context_prompt(
        self,
        question: str,
        chunks: list[RetrievedChunk],
    ) -> tuple[str, dict[int, RetrievedChunk]]:
        """Formats numbered citation sources and assembles the user prompt."""
        context_blocks = []
        source_map: dict[int, RetrievedChunk] = {}

        for idx, chunk in enumerate(chunks, start=1):
            source_map[idx] = chunk
            title = chunk.source.document_title or chunk.source.filename
            section = chunk.source.section_heading or "General"
            block = (
                f"[{idx}] Document: {title} | File: {chunk.source.filename} | Section: {section}\n"
                f"{chunk.content.strip()}"
            )
            context_blocks.append(block)

        context_str = "\n\n".join(context_blocks)
        prompt = (
            f"SOURCES:\n"
            f"{context_str}\n\n"
            f"QUESTION: {question}\n\n"
            f"GROUNDED ANSWER (with [N] citations):"
        )
        return prompt, source_map

    def _extract_citations(
        self,
        answer: str,
        source_map: dict[int, RetrievedChunk],
    ) -> list[CitationItem]:
        """Extracts [N] bracket citations from generated text and builds citation lineage items."""
        # Find all [N] numbers in the answer
        raw_ids = re.findall(r"\[(\d+)\]", answer)
        cited_indices = list(dict.fromkeys(int(i) for i in raw_ids if int(i) in source_map))

        citations: list[CitationItem] = []
        for c_id in cited_indices:
            chunk = source_map[c_id]
            snippet = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
            citations.append(
                CitationItem(
                    citation_id=c_id,
                    document_id=chunk.source.document_id,
                    filename=chunk.source.filename,
                    document_title=chunk.source.document_title,
                    page_number=chunk.source.page_number,
                    section_heading=chunk.source.section_heading,
                    heading_hierarchy=chunk.source.heading_hierarchy,
                    snippet=snippet,
                )
            )
        return citations

    async def answer(
        self,
        db: AsyncSession,
        user: User,
        request: RAGQueryRequest,
    ) -> RAGQueryResponse:
        """Executes full RAG pipeline: Hybrid Retrieval -> Grounded Prompt -> LLM -> Citations."""
        # 1. Retrieve ranked candidates with security pre-filters
        chunks = await self.retrieval_service.search(
            db=db,
            user=user,
            query=request.question,
            top_k=request.top_k,
            top_n=request.top_n,
            score_threshold=request.score_threshold,
            max_tokens=request.max_tokens,
        )

        if not chunks:
            return RAGQueryResponse(
                question=request.question,
                answer="I do not have sufficient information in the provided documentation to answer this question.",
                citations=[],
                has_sufficient_context=False,
                model=settings.ACTIVE_LLM_MODEL,
            )

        # 2. Build grounded prompt and source mapping
        prompt, source_map = self._build_context_prompt(request.question, chunks)

        # 3. Generate grounded answer from LLM
        raw_answer = await self.llm_client.generate_text(
            prompt=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=request.temperature,
        )

        # 4. Extract citations and check sufficiency
        citations = self._extract_citations(raw_answer, source_map)
        has_sufficient = INSUFFICIENT_INFO_PHRASE not in raw_answer.lower()

        return RAGQueryResponse(
            question=request.question,
            answer=raw_answer.strip(),
            citations=citations,
            has_sufficient_context=has_sufficient,
            model=settings.ACTIVE_LLM_MODEL,
        )

    async def stream_answer(
        self,
        db: AsyncSession,
        user: User,
        request: RAGQueryRequest,
    ) -> AsyncGenerator[str, None]:
        """Streams answer tokens via Server-Sent Events (SSE) and emits a terminal citation manifest."""
        # 1. Retrieve candidates
        chunks = await self.retrieval_service.search(
            db=db,
            user=user,
            query=request.question,
            top_k=request.top_k,
            top_n=request.top_n,
            score_threshold=request.score_threshold,
            max_tokens=request.max_tokens,
        )

        if not chunks:
            yield f"data: {json.dumps({'token': 'I do not have sufficient information in the provided documentation to answer this question.'})}\n\n"
            yield f"data: {json.dumps({'event': 'done', 'citations': [], 'has_sufficient_context': False})}\n\n"
            return

        # 2. Build prompt
        prompt, source_map = self._build_context_prompt(request.question, chunks)

        # 3. Stream tokens
        full_text = ""
        async for token in self.llm_client.stream_text(
            prompt=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=request.temperature,
        ):
            full_text += token
            yield f"data: {json.dumps({'token': token})}\n\n"

        # 4. Post-process citations from complete streamed text
        citations = self._extract_citations(full_text, source_map)
        has_sufficient = INSUFFICIENT_INFO_PHRASE not in full_text.lower()

        done_payload = {
            "event": "done",
            "has_sufficient_context": has_sufficient,
            "citations": [c.model_dump(mode="json") for c in citations],
        }
        yield f"data: {json.dumps(done_payload)}\n\n"
