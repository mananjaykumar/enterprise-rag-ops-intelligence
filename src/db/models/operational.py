import datetime
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Department(Base):
    """Department operational entity."""

    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default_tenant")
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    annual_budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    employees: Mapped[list["Employee"]] = relationship("Employee", back_populates="department")
    expenses: Mapped[list["OperationalExpense"]] = relationship(
        "OperationalExpense", back_populates="department"
    )


class Employee(Base):
    """Employee organizational entity."""

    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default_tenant")
    employee_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False)
    role_title: Mapped[str] = mapped_column(String(128), nullable=False)
    employment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    hire_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    department: Mapped["Department"] = relationship("Department", back_populates="employees")
    expenses: Mapped[list["OperationalExpense"]] = relationship(
        "OperationalExpense", back_populates="employee"
    )


class Vendor(Base):
    """External vendor operational entity."""

    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default_tenant")
    vendor_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_rating: Mapped[str] = mapped_column(String(16), nullable=False, default="LOW")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    contracts: Mapped[list["Contract"]] = relationship("Contract", back_populates="vendor")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="vendor")


class Contract(Base):
    """Vendor contract entity bridging documents to SQL."""

    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False
    )
    associated_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default_tenant")
    contract_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="contracts")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="contract")


class Invoice(Base):
    """Vendor billing invoice."""

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=True
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default_tenant")
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    paid_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="invoices")
    contract: Mapped["Contract | None"] = relationship("Contract", back_populates="invoices")


class OperationalExpense(Base):
    """Departmental operational line-item expense."""

    __tablename__ = "operational_expenses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default_tenant")
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    expense_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    department: Mapped["Department"] = relationship("Department", back_populates="expenses")
    employee: Mapped["Employee"] = relationship("Employee", back_populates="expenses")


class SqlQueryAuditLog(Base):
    """Immutable audit trail for all Text-to-SQL executions."""

    __tablename__ = "sql_query_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False)
    sanitized_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'SUCCESS', 'BLOCKED', 'ERROR'
    execution_time_ms: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    rows_returned: Mapped[int] = mapped_column(nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
