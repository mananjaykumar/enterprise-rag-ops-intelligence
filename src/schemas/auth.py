import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.db.models.user import UserRole


# 1. Request Schemas
class UserRegisterRequest(BaseModel):
    """Payload for creating a new user account."""

    email: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="User work email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password (minimum 8 characters)",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Full legal or display name",
    )
    role: UserRole = Field(
        default=UserRole.ANALYST,
        description="Assigned RBAC role",
    )
    tenant_id: str = Field(
        default="default_tenant",
        min_length=1,
        max_length=64,
        description="Enterprise tenant identifier",
    )


class LoginRequest(BaseModel):
    """Payload for user authentication."""

    email: str = Field(..., description="Registered user email")
    password: str = Field(..., description="User account password")
    tenant_id: str = Field(
        default="default_tenant",
        description="Enterprise tenant identifier",
    )


# 2. Response Schemas
class UserResponse(BaseModel):
    """Public user profile (excludes sensitive password hashes)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """OAuth2-compatible Bearer access token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
