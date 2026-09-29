import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.operational import SqlQueryAuditLog
from src.db.models.user import User
from src.domain.interfaces.llm import BaseLLMClient
from src.infrastructure.ai.gemini_llm import GeminiLLMClient
from src.schemas.sql import NaturalLanguageSQLRequest, SQLQueryResult
from src.services.sql_sandbox import SQLSandboxService, SQLSecurityViolation

logger = logging.getLogger(__name__)

SCHEMA_METADATA = """
PostgreSQL Operational Business Database Tables:
1. departments:
   - id: UUID (PK)
   - tenant_id: VARCHAR(64)
   - code: VARCHAR(16) UNIQUE (e.g., 'ENG', 'FIN', 'OPS')
   - name: VARCHAR(128)
   - annual_budget: NUMERIC(14,2)

2. employees:
   - id: UUID (PK)
   - department_id: UUID (FK -> departments.id)
   - tenant_id: VARCHAR(64)
   - employee_code: VARCHAR(32) UNIQUE
   - full_name: VARCHAR(128)
   - email: VARCHAR(128)
   - role_title: VARCHAR(128)
   - employment_status: VARCHAR(32) ('ACTIVE', 'TERMINATED')
   - hire_date: DATE

3. vendors:
   - id: UUID (PK)
   - tenant_id: VARCHAR(64)
   - vendor_code: VARCHAR(32) UNIQUE
   - name: VARCHAR(255)
   - category: VARCHAR(64) ('Software', 'Logistics', 'Consulting')
   - risk_rating: VARCHAR(16) ('LOW', 'MEDIUM', 'HIGH')
   - is_active: BOOLEAN

4. contracts:
   - id: UUID (PK)
   - vendor_id: UUID (FK -> vendors.id)
   - associated_document_id: UUID (FK -> documents.id, nullable)
   - tenant_id: VARCHAR(64)
   - contract_number: VARCHAR(64) UNIQUE
   - title: VARCHAR(255)
   - total_value: NUMERIC(14,2)
   - start_date: DATE
   - end_date: DATE
   - auto_renew: BOOLEAN
   - status: VARCHAR(32) ('ACTIVE', 'EXPIRED', 'PENDING')

5. invoices:
   - id: UUID (PK)
   - vendor_id: UUID (FK -> vendors.id)
   - contract_id: UUID (FK -> contracts.id, nullable)
   - tenant_id: VARCHAR(64)
   - invoice_number: VARCHAR(64)
   - amount: NUMERIC(14,2)
   - issue_date: DATE
   - due_date: DATE
   - payment_status: VARCHAR(32) ('PENDING', 'PAID', 'OVERDUE')
   - paid_at: TIMESTAMPTZ (nullable)

6. operational_expenses:
   - id: UUID (PK)
   - department_id: UUID (FK -> departments.id)
   - employee_id: UUID (FK -> employees.id)
   - tenant_id: VARCHAR(64)
   - category: VARCHAR(64) ('Travel', 'Software', 'Supplies', 'Meals')
   - amount: NUMERIC(10,2)
   - currency: VARCHAR(3) ('USD')
   - expense_date: DATE
   - description: TEXT
   - approved: BOOLEAN
"""

SQL_SYSTEM_INSTRUCTION = """You are a senior PostgreSQL data engineer for an enterprise operational database.
Your job is to translate user natural language queries into efficient, valid PostgreSQL SELECT queries.

STRICT RULES:
1. Generate ONLY ONE valid SELECT query.
2. NEVER use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.
3. NEVER query tables outside the provided operational schema. Do NOT query 'users' or 'documents'.
4. Use standard JOIN clauses using the defined foreign keys.
5. Aggregate functions (SUM, AVG, COUNT, MIN, MAX) should include proper GROUP BY clauses.
6. Return ONLY the raw SQL query. Do not wrap in markdown or explanation.
"""


class TextToSQLService:
    """End-to-end Text-to-SQL translation, 5-gate sandbox validation, execution, and explanation."""

    def __init__(
        self,
        llm_client: BaseLLMClient | None = None,
        sandbox_service: SQLSandboxService | None = None,
    ) -> None:
        self.llm_client = llm_client or GeminiLLMClient()
        self.sandbox = sandbox_service or SQLSandboxService()

    async def _audit_log(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        prompt: str,
        generated_sql: str,
        sanitized_sql: str | None,
        status: str,
        execution_time_ms: float,
        rows_returned: int,
        error_message: str | None,
    ) -> None:
        """Persists query execution audit entry."""
        audit_entry = SqlQueryAuditLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            user_prompt=prompt,
            generated_sql=generated_sql,
            sanitized_sql=sanitized_sql,
            execution_status=status,
            execution_time_ms=execution_time_ms,
            rows_returned=rows_returned,
            error_message=error_message,
        )
        db.add(audit_entry)
        try:
            await db.commit()
        except Exception as exc:
            logger.error("Failed to commit SQL audit log: %s", exc)
            await db.rollback()

    async def execute_query(
        self,
        db: AsyncSession,
        user: User,
        request: NaturalLanguageSQLRequest,
    ) -> SQLQueryResult:
        """Translates natural language to SQL, validates via 5-gate sandbox, executes, and audits."""
        # Extract scalar identity strings before any DB execution / rollback expires the ORM object
        user_tenant_id = str(user.tenant_id)
        user_id_str = str(user.id)
        # 1. Generate candidate SQL via Gemini
        prompt = (
            f"SCHEMA:\n{SCHEMA_METADATA}\n\n"
            f"USER QUERY: {request.prompt}\n\n"
            f"POSTGRESQL SELECT QUERY:"
        )
        generated_sql = await self.llm_client.generate_text(
            prompt=prompt,
            system_instruction=SQL_SYSTEM_INSTRUCTION,
            temperature=0.0,
        )

        sanitized_sql = None
        # 2. 5-Gate Sandbox AST Validation & Tenant Injection
        try:
            sanitized_sql = self.sandbox.validate_and_sanitize(
                raw_sql=generated_sql,
                tenant_id=user_tenant_id,
            )
        except SQLSecurityViolation as sec_err:
            await self._audit_log(
                db=db,
                tenant_id=user_tenant_id,
                user_id=user_id_str,
                prompt=request.prompt,
                generated_sql=generated_sql,
                sanitized_sql=None,
                status="BLOCKED",
                execution_time_ms=0.0,
                rows_returned=0,
                error_message=str(sec_err),
            )
            raise

        # 3. Read-Only Transaction Execution
        try:
            columns, rows, exec_ms = await self.sandbox.execute_readonly_query(
                db=db,
                sanitized_sql=sanitized_sql,
            )
        except Exception as query_err:
            await self._audit_log(
                db=db,
                tenant_id=user_tenant_id,
                user_id=user_id_str,
                prompt=request.prompt,
                generated_sql=generated_sql,
                sanitized_sql=sanitized_sql,
                status="ERROR",
                execution_time_ms=0.0,
                rows_returned=0,
                error_message=str(query_err),
            )
            raise

        # 4. Successful Audit Logging
        await self._audit_log(
            db=db,
            tenant_id=user_tenant_id,
            user_id=user_id_str,
            prompt=request.prompt,
            generated_sql=generated_sql,
            sanitized_sql=sanitized_sql,
            status="SUCCESS",
            execution_time_ms=exec_ms,
            rows_returned=len(rows),
            error_message=None,
        )

        # 5. Optional Natural Language Explanation
        explanation = None
        if request.explain and rows:
            explain_prompt = (
                f"QUESTION: {request.prompt}\n"
                f"SQL: {sanitized_sql}\n"
                f"DATA ROWS: {rows[:10]}\n\n"
                f"Summarize these findings in 1-2 clear, business-friendly sentences."
            )
            explanation = await self.llm_client.generate_text(
                prompt=explain_prompt,
                temperature=0.0,
            )

        return SQLQueryResult(
            prompt=request.prompt,
            generated_sql=generated_sql.strip(),
            sanitized_sql=sanitized_sql,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=exec_ms,
            explanation=explanation.strip() if explanation else None,
        )
