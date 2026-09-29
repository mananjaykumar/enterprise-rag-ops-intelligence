import logging
import time
from typing import Any

import sqlglot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp

logger = logging.getLogger(__name__)

ALLOWED_TABLES = {
    "departments",
    "employees",
    "vendors",
    "contracts",
    "invoices",
    "operational_expenses",
}

DISALLOWED_FUNCTIONS = {
    "pg_sleep",
    "pg_read_file",
    "pg_write_file",
    "pg_ls_dir",
    "version",
    "current_version",
    "currentversion",
    "current_user",
    "currentuser",
    "session_user",
    "sessionuser",
    "current_database",
    "currentdatabase",
    "inet_client_addr",
    "inet_server_addr",
}


class SQLSecurityViolation(Exception):
    """Raised when generated SQL violates sandbox security boundaries."""

    pass


class SQLSandboxService:
    """5-Gate Defense-in-Depth SQL AST Parser and Sandbox Executor."""

    def __init__(self, allowed_tables: set[str] | None = None) -> None:
        self.allowed_tables = allowed_tables or ALLOWED_TABLES

    def validate_and_sanitize(self, raw_sql: str, tenant_id: str) -> str:
        """Validates, sanitizes, and injects tenant and limit constraints into the AST.

        Raises:
            SQLSecurityViolation: If the query violates read-only or schema boundaries.
        """
        # Clean markdown codeblocks if LLM returned them
        clean_sql = raw_sql.strip()
        if clean_sql.startswith("```"):
            lines = clean_sql.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_sql = "\n".join(lines).strip()

        # Gate 2: AST Parsing & Single Statement Check
        try:
            parsed_list = sqlglot.parse(clean_sql, read="postgres")
        except Exception as exc:
            raise SQLSecurityViolation(f"SQL Syntax Error: Could not parse query: {exc}") from exc

        if not parsed_list or len(parsed_list) != 1 or parsed_list[0] is None:
            raise SQLSecurityViolation(
                "Multi-statement execution rejected. Query must contain exactly one SQL statement."
            )

        expr = parsed_list[0]

        # Gate 2: Reject non-SELECT root AST
        if not isinstance(expr, exp.Select):
            raise SQLSecurityViolation(
                f"Destructive operation rejected. Only read-only SELECT statements are permitted, got: {expr.key.upper()}"
            )

        # Gate 3: Schema Table Whitelist Check
        tables_referenced = {table.name.lower() for table in expr.find_all(exp.Table)}
        if not tables_referenced:
            raise SQLSecurityViolation("Query must reference at least one valid business table.")

        unauthorized_tables = tables_referenced - self.allowed_tables
        if unauthorized_tables:
            raise SQLSecurityViolation(
                f"Access denied: Query attempts to read restricted or non-whitelisted tables: {unauthorized_tables}"
            )

        # Gate 3: Prohibited Functions Check
        disallowed_normalized = {f.lower().replace("_", "") for f in DISALLOWED_FUNCTIONS}
        for func_node in expr.find_all(exp.Func, exp.Anonymous):
            func_name = (func_node.name or type(func_node).__name__ or func_node.key or "").lower()
            if (
                func_name in DISALLOWED_FUNCTIONS
                or func_name.replace("_", "") in disallowed_normalized
            ):
                raise SQLSecurityViolation(
                    f"Forbidden SQL function '{func_name}' is not permitted in sandbox."
                )

        # Gate 4: Multi-Tenant AST Injection for all referenced tables
        for table in expr.find_all(exp.Table):
            alias = table.alias or table.name
            tenant_filter = sqlglot.parse_one(f"{alias}.tenant_id = '{tenant_id}'", read="postgres")
            expr = expr.where(tenant_filter, copy=False)

        # Gate 5: Limit Enforcement
        limit_node = expr.find(exp.Limit)
        if not limit_node:
            expr = expr.limit(100)
        else:
            try:
                val = int(str(limit_node.expression))
                if val > 100 or val <= 0:
                    limit_node.set("expression", exp.Literal.number(100))
            except Exception:
                limit_node.set("expression", exp.Literal.number(100))

        return expr.sql("postgres")

    async def execute_readonly_query(
        self,
        db: AsyncSession,
        sanitized_sql: str,
        statement_timeout_ms: int = 3000,
    ) -> tuple[list[str], list[dict[str, Any]], float]:
        """Executes sanitized query inside a read-only transaction with execution timeout."""
        start_time = time.perf_counter()

        # Enforce statement timeout and read-only transaction isolation
        await db.execute(text(f"SET statement_timeout = {statement_timeout_ms};"))
        await db.execute(text("SET TRANSACTION READ ONLY;"))

        try:
            result = await db.execute(text(sanitized_sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
        finally:
            # Release read-only transaction so session is write-capable for audit logging
            await db.rollback()

        # Convert non-JSON serializable types (Decimals, Dates) to str
        serialized_rows = []
        for r in rows:
            clean_row = {}
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    clean_row[k] = v.isoformat()
                elif hasattr(v, "__str__") and type(v).__name__ == "Decimal":
                    clean_row[k] = float(v)
                else:
                    clean_row[k] = v
            serialized_rows.append(clean_row)

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return columns, serialized_rows, execution_time_ms
