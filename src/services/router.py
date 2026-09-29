import json
import logging
import re
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces.llm import BaseLLMClient
from src.infrastructure.ai.gemini_llm import GeminiLLMClient
from src.schemas.agent import ExecutionRoute

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory document catalog cache
# ---------------------------------------------------------------------------
_DOC_CATALOG_CACHE: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL_SECONDS = 60.0


async def get_active_document_titles(db: AsyncSession | None, tenant_id: str | None) -> list[str]:
    """Retrieves titles of active ingested documents for a tenant, cached for 60s."""
    if not db or not tenant_id:
        return []

    now = time.time()
    cached = _DOC_CATALOG_CACHE.get(tenant_id)
    if cached and (now - cached[0] < _CACHE_TTL_SECONDS):
        return cached[1]

    try:
        result = await db.execute(
            text("SELECT title FROM documents WHERE tenant_id = :tenant_id AND is_active = true"),
            {"tenant_id": tenant_id},
        )
        titles = [row[0] for row in result.fetchall() if row[0]]
        _DOC_CATALOG_CACHE[tenant_id] = (now, titles)
        return titles
    except Exception as exc:
        logger.warning("Could not fetch active document titles: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Keyword heuristic tables
# ---------------------------------------------------------------------------

# Phrases / words that strongly signal an unstructured document query
_RAG_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"\bpolic(?:y|ies)\b",
        r"\bguideline(?:s)?\b",
        r"\bprocedure(?:s)?\b",
        r"\bhandbook(?:s)?\b",
        r"\bmanual(?:s)?\b",
        r"\bclause(?:s)?\b",
        r"\bprovisions?\b",
        r"\bsop(?:s)?\b",
        r"\ballowance(?:s)?\b",
        r"\bcommission(?:s)?\b",
        r"\bstructure(?:s)?\b",
        r"\bfee schedule\b",
        r"\bpricing structure\b",
        r"\brate card\b",
        r"\bpricing\b",
        r"\btier(?:s)?\b",
        r"\bslab(?:s)?\b",
        r"\bterms (?:and|&) conditions\b",
        r"\bterms of (?:service|agreement|contract)\b",
        r"\bpayment terms\b",
        r"\bmou\b",
        r"\bagreement(?:s)?\b",
        r"\bsla(?:s)?\b",
        r"\bservice level\b",
        r"\bpenalt(?:y|ies)\b",
        r"\bdeliverable(?:s)?\b",
        r"\bscope of work\b",
        r"\btermination (?:clause|terms)?\b",
        r"\bconfidentiality\b",
        r"\bnon.?disclosure\b",
        r"\bwarrant(?:y|ies)\b",
        r"\bindemnif(?:y|ication)\b",
        r"\bresponsibilit(?:y|ies)\b",
        r"\bobligations?\b",
        r"\bspecifications?\b",
        r"\btravel\b",
        r"\bhotel(?:s)?\b",
        r"\bflight(?:s)?\b",
        r"\blodging\b",
        r"\bboarding\b",
        r"\bper.?diem\b",
        r"\bconveyance\b",
        r"\bmeal allowance\b",
        r"\bdaily allowance\b",
        r"\bentitle(?:ment|d)?\b",
        r"\brules?\b",
        r"\beligibilit(?:y|ies)\b",
        r"\bcompliance\b",
        r"\bregulation(?:s)?\b",
        r"\baccuracy\b",
        r"\bclassif(?:y|ication|ied)\b",
        r"\bresearch\b",
        r"\bpaper(?:s)?\b",
        r"\bstudy\b",
        r"\bmethod(?:ology)?\b",
        r"\balgorithm(?:s)?\b",
        r"\barchitecture(?:s)?\b",
        r"\bmodel(?:s)?\b",
        r"\bdataset(?:s)?\b",
        r"\bexperiment(?:s)?\b",
        r"\bperformance\b",
        r"\bprecision\b",
        r"\brecall\b",
        r"\bf1.score\b",
        r"\bbaseline(?:s)?\b",
        r"\btraining\b",
        r"\binference\b",
        r"\bremote.?work\b",
        r"\bwork.?from.?home\b",
        r"\bwfh\b",
        r"\bstandard operating\b",
        r"\bcode of conduct\b",
        r"\bleave polic\b",
        r"\bwork polic\b",
        r"\btime.?off\b",
        r"\bbenefits\b",
        r"\bdocumentation\b",
    ]
]


# Phrases / words that strongly signal a structured database query
_SQL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"\bhow many\b",
        r"\btotal\b",
        r"\bsum\b",
        r"\baverage\b",
        r"\bcount\b",
        r"\blist (?:all|the|me)\b",
        r"\bshow (?:all|the|me)\b",
        r"\bget (?:all|the|me)\b",
        r"\bfetch (?:all|the)\b",
        r"\bbudget(?:s)?\b",
        r"\brevenue(?:s)?\b",
        r"\bexpense(?:s)?\b",
        r"\binvoice(?:s)?\b",
        r"\bsalar(?:y|ies)\b",
        r"\bheadcount\b",
        r"\bhired\b",
        r"\bspent\b",
        r"\bvendor(?:s)?\b",
        r"\bdepartment(?:s)?\b",
        r"\bemployee(?:s)?\b",
        r"\btop \d+\b",
        r"\bactive (?:vendor|contract|employee)s?\b",
        r"\blow risk\b",
    ]
]

# Phrases that indicate a cross-reference / comparison between both sources
_HYBRID_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"\bcompar(?:e|ing|ison)\b",
        r"\baudit\b",
        r"\bnon.?compli(?:ant|ance)\b",
        r"\bvarian(?:ce|t)\b",
        r"\bexceed\b",
        r"\bover.?run\b",
        r"\bcheck (?:if|whether|that)\b",
        r"\bverif(?:y|ication)\b",
        r"\bvs\.?\b",
        r"\bagainst\b",
        r"\bcross.?refer\b",
    ]
]

# Minimum score difference required to trust the heuristic when both sides match
_CONFIDENCE_THRESHOLD = 2


def _matches_document_catalog(prompt: str, document_titles: list[str]) -> str | None:
    """Checks whether distinctive terms from any ingested document title appear in the prompt.

    Handles spelling variations (e.g. 'manpaya' vs 'Manpaaya') and compound names.
    Returns the matching document title if found, or None.
    """
    if not document_titles:
        return None

    prompt_lower = prompt.lower()
    prompt_words = re.findall(r"\b\w+\b", prompt_lower)

    # Common generic words that alone do not identify a specific document
    generic_words = {
        "contract",
        "service",
        "services",
        "policy",
        "policies",
        "document",
        "documents",
        "agreement",
        "guideline",
        "guidelines",
        "main",
        "draft",
        "final",
        "file",
        "pdf",
    }

    for title in document_titles:
        title_lower = title.lower()
        title_words = [
            w
            for w in re.findall(r"\b\w+\b", title_lower)
            if len(w) >= 4 and w not in generic_words
        ]

        for tw in title_words:
            # 1. Exact token or substring match
            if tw in prompt_words or tw in prompt_lower:
                return title

            # 2. Fuzzy match for spelling variants (e.g. manpaya <-> manpaaya, tiffin <-> tiffins)
            for pw in prompt_words:
                if len(pw) >= 5 and len(tw) >= 5:
                    if pw.startswith(tw[:5]) or tw.startswith(pw[:5]):
                        return title

    return None


def _heuristic_route(
    prompt: str,
    document_titles: list[str] | None = None,
) -> tuple[ExecutionRoute, str] | None:
    """Scores the query against keyword tables and document catalog.

    Returns (route, reasoning) if confident, or None when ambiguous.
    """
    # 1. Explicit hybrid signals override everything
    if any(p.search(prompt) for p in _HYBRID_PATTERNS):
        return (
            ExecutionRoute.HYBRID_AGENT,
            "Keyword heuristic detected cross-referencing/compliance audit intent — routed to Hybrid Agent.",
        )

    # 2. Check if the query refers to an active ingested document
    matched_doc = _matches_document_catalog(prompt, document_titles or [])
    rag_score = sum(1 for p in _RAG_PATTERNS if p.search(prompt))
    sql_score = sum(1 for p in _SQL_PATTERNS if p.search(prompt))

    # If the query names an ingested document and asks for text/terms/structure/clauses
    if matched_doc:
        # If it doesn't ask for pure SQL aggregations like count or total expenses
        if sql_score == 0 or rag_score >= 1:
            return (
                ExecutionRoute.RAG,
                f"Query refers to ingested document '{matched_doc}' — routed to RAG for document retrieval.",
            )

    logger.debug(
        "Heuristic scores — RAG: %d, SQL: %d (matched_doc: %s, query: %.60s…)",
        rag_score,
        sql_score,
        matched_doc,
        prompt,
    )

    # Decisive one-sided match
    if rag_score >= 1 and sql_score == 0:
        return (
            ExecutionRoute.RAG,
            "Keyword heuristic detected document/research query — routed to RAG.",
        )
    if sql_score >= 1 and rag_score == 0:
        return (
            ExecutionRoute.SQL,
            "Keyword heuristic detected structured data query — routed to SQL.",
        )

    # Mixed matches - require threshold margin
    delta = rag_score - sql_score
    if delta >= _CONFIDENCE_THRESHOLD:
        return (
            ExecutionRoute.RAG,
            "Keyword heuristic detected predominantly document query — routed to RAG.",
        )
    if -delta >= _CONFIDENCE_THRESHOLD:
        return (
            ExecutionRoute.SQL,
            "Keyword heuristic detected predominantly structured query — routed to SQL.",
        )

    # Not confident enough — let the LLM decide
    return None


ROUTER_SYSTEM_INSTRUCTION = """You are an expert query intent router for an enterprise intelligence platform.
Your job is to analyze the user query and classify it into exactly one of three execution pathways:

1. 'RAG' (Unstructured Document Retrieval):
   - The query asks about information stored inside unstructured documents, PDFs, policies, or contracts.
   - Examples of RAG queries:
     * Commission structures, fee schedules, pricing models, mess/delivery shares in contracts.
     * Specific contract clauses, terms, conditions, payment terms, SLAs, deliverables, penalties, scopes of work.
     * Company policies, employee handbooks, travel allowances, SOPs, research papers, technical specs.
   - CRITICAL ARCHITECTURAL BOUNDARY: The operational SQL database does NOT store document text, contract clauses, or commission structures. If a query asks for a "commission structure", "contract terms", "payment terms", "pricing tiers", or "provisions" of any vendor/contract/policy, it MUST be routed to 'RAG'.

2. 'SQL' (Structured Operational Database Query):
   - The query asks for quantitative aggregations, counts, sums, averages, lists, or filters from the structured operational database.
   - Available SQL tables and columns:
     * departments: id, code, name, annual_budget
     * employees: id, employee_code, full_name, email, role_title, employment_status, hire_date
     * vendors: id, vendor_code, name, category, risk_score, status
     * contracts: id, contract_number, vendor_id, title, total_value, start_date, end_date, status
     * invoices: id, invoice_number, contract_id, amount, status, invoice_date, due_date
     * operational_expenses: id, expense_number, department_id, employee_id, expense_category, amount, expense_date, merchant, description
   - Examples:
     * 'What is the annual budget of the Marketing department?'
     * 'List all active software vendors with low risk ratings'
     * 'How many employees were hired this year?'
     * 'Total amount of all unpaid invoices'

3. 'HYBRID_AGENT' (Multi-Step Cross-Referencing & Audit):
   - The query requires comparing or verifying unstructured document rules/contracts against structured database numbers.
   - Involves compliance audits, variance checks, or multi-step analysis combining both documents and database tables.
   - Examples:
     * 'Compare our travel policy daily allowance limits with actual Engineering expenses to find non-compliant claims.'
     * 'Check if vendor invoice totals exceed the agreed contract values.'
     * 'Audit employee meal expenses against the spending rules in the company handbook.'

STRICT RESPONSE FORMAT:
Return ONLY a valid JSON object with no markdown wrapping:
{"route": "RAG" | "SQL" | "HYBRID_AGENT", "reasoning": "Brief 1-sentence plain English explanation"}
"""


class QueryRouterService:
    """Classifies user queries to dispatch them to RAG, SQL, or Stateful Agent pathways.

    Classification is a two-stage pipeline:
    1. Fast heuristic + document catalog awareness (~0 ms) — detects known documents,
       commission structures, policy clauses, or structured metrics without an API call.
    2. LLM fallback (~2–4 s) with schema & document catalog context — fires only when ambiguous.
    """

    def __init__(self, llm_client: BaseLLMClient | None = None) -> None:
        self.llm_client = llm_client or GeminiLLMClient()

    async def route_query(
        self,
        prompt: str,
        force_route: ExecutionRoute | None = None,
        db: AsyncSession | None = None,
        tenant_id: str | None = None,
    ) -> tuple[ExecutionRoute, str]:
        """Classifies the execution pathway for a user query.

        Args:
            prompt: User natural language input.
            force_route: Optional explicit route override.
            db: Optional async database session to fetch active document catalog.
            tenant_id: Optional tenant identifier for document catalog scope.

        Returns:
            Tuple of (selected ExecutionRoute, explanation string).
        """
        # Hard override — always respected
        if force_route:
            return force_route, f"Manual route override selected: {force_route.value}"

        # Fetch active document catalog for semantic and entity matching
        active_docs = await get_active_document_titles(db, tenant_id)

        # --- Stage 1: Fast heuristic + document catalog matching ---
        heuristic_res = _heuristic_route(prompt, document_titles=active_docs)
        if heuristic_res is not None:
            route, reason = heuristic_res
            logger.info(
                "Heuristic classified query as %s (skipping LLM router call): %.60s…",
                route.value,
                prompt,
            )
            return route, reason

        # --- Stage 2: LLM fallback with grounded knowledge base context ---
        logger.info("Heuristic inconclusive — calling LLM router for: %.60s…", prompt)

        doc_context = ""
        if active_docs:
            doc_bullets = "\n".join(f"- {d}" for d in active_docs[:20])
            doc_context = f"\nINGESTED DOCUMENTS IN KNOWLEDGE BASE:\n{doc_bullets}\n"

        router_prompt = f"{doc_context}\nUSER QUERY: {prompt}\n\nCLASSIFICATION JSON:"

        try:
            raw_response = await self.llm_client.generate_text(
                prompt=router_prompt,
                system_instruction=ROUTER_SYSTEM_INSTRUCTION,
                temperature=0.0,
            )

            clean_json = raw_response.strip()
            if clean_json.startswith("```"):
                lines = clean_json.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                clean_json = "\n".join(lines).strip()

            parsed: dict[str, Any] = json.loads(clean_json)
            route_str = str(parsed.get("route", "")).upper()
            reasoning = str(parsed.get("reasoning", "Classified by intent router."))

            if route_str in ExecutionRoute.__members__:
                return ExecutionRoute(route_str), reasoning

            logger.warning(
                "Unrecognized route '%s' returned by LLM classifier; defaulting to HYBRID_AGENT",
                route_str,
            )
            return ExecutionRoute.HYBRID_AGENT, "Complex intent detected; routed to hybrid agent."

        except Exception as exc:
            logger.error(
                "Query classification failed with error: %s; fallback to HYBRID_AGENT", exc
            )
            return ExecutionRoute.HYBRID_AGENT, f"Classifier fallback due to error: {exc}"
