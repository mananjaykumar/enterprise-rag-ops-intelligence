import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NaturalLanguageSQLRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=2,
        max_length=2000,
        description="Natural language question about business operations",
    )
    explain: bool = Field(
        default=True,
        description="Whether to generate a natural language explanation of the resulting data",
    )


class SQLQueryResult(BaseModel):
    prompt: str
    generated_sql: str
    sanitized_sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
    explanation: str | None = None


class SQLAuditLogResponse(BaseModel):
    id: uuid.UUID
    tenant_id: str
    user_id: str
    user_prompt: str
    generated_sql: str
    sanitized_sql: str | None
    execution_status: str
    execution_time_ms: float
    rows_returned: int
    error_message: str | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
