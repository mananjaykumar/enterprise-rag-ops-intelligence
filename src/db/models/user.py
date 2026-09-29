import enum
import uuid

from sqlalchemy import Boolean, Enum, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin


class UserRole(enum.StrEnum):
    """Enterprise Role-Based Access Control tiers."""

    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"


class User(Base, TimestampMixin):
    """User account entity with multi-tenant and RBAC attributes."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="default_tenant",
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", native_enum=True),
        nullable=False,
        default=UserRole.ANALYST,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    def __repr__(self) -> str:
        return f"<User email={self.email!r} role={self.role.value!r} tenant={self.tenant_id!r}>"
