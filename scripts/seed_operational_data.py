"""
Enterprise Database Seeding Script for Text-to-SQL Demonstration.

Seeds:
1. Administrator User: admin@gmail.com (Password: Admin@12345)
2. Operational Schema Entities:
   - Departments (ENG, MKT, FIN, HR, SEC)
   - Employees (with real foreign keys to departments)
   - Vendors (with categories, risk ratings, active status)
   - Contracts (with contract values, date ranges, statuses)
   - Invoices (with amounts, due dates, statuses, paid dates)
   - Operational Expenses (with categories, amounts, approval status, dual FK to dept & emp)

Usage:
    .venv/bin/python scripts/seed_operational_data.py
"""

import asyncio
import datetime
import logging
import os
import sys
import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.db.models.operational import (
    Contract,
    Department,
    Employee,
    Invoice,
    OperationalExpense,
    Vendor,
)
from src.db.models.user import User, UserRole
from src.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_operational_data")

TENANT_ID = os.getenv("SEED_TENANT_ID", "default_tenant")
ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@gmail.com")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "Admin@12345")


async def seed_admin_user(session: AsyncSession) -> User:
    """Creates or updates the demo Admin user."""
    stmt = select(User).where(User.email == ADMIN_EMAIL, User.tenant_id == TENANT_ID)
    result = await session.execute(stmt)
    existing_admin = result.scalar_one_or_none()

    hashed_pw = hash_password(ADMIN_PASSWORD)

    if existing_admin:
        existing_admin.role = UserRole.ADMIN
        existing_admin.hashed_password = hashed_pw
        existing_admin.full_name = "Enterprise System Admin"
        existing_admin.is_active = True
        logger.info(f"Updated existing Admin user: {ADMIN_EMAIL}")
        return existing_admin
    else:
        new_admin = User(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            email=ADMIN_EMAIL,
            full_name="Enterprise System Admin",
            hashed_password=hashed_pw,
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(new_admin)
        logger.info(f"Created new Admin user: {ADMIN_EMAIL}")
        return new_admin


async def clear_operational_data(session: AsyncSession) -> None:
    """Cleans up existing operational demo records in foreign-key safe order."""
    logger.info("Cleaning up old operational demo records for tenant %s...", TENANT_ID)
    await session.execute(
        delete(OperationalExpense).where(OperationalExpense.tenant_id == TENANT_ID)
    )
    await session.execute(delete(Invoice).where(Invoice.tenant_id == TENANT_ID))
    await session.execute(delete(Contract).where(Contract.tenant_id == TENANT_ID))
    await session.execute(delete(Vendor).where(Vendor.tenant_id == TENANT_ID))
    await session.execute(delete(Employee).where(Employee.tenant_id == TENANT_ID))
    await session.execute(delete(Department).where(Department.tenant_id == TENANT_ID))
    await session.flush()


async def seed_operational_entities(session: AsyncSession) -> dict[str, int]:
    """Populates operational tables with rich, relational demo data."""
    # 1. Departments
    dept_eng = Department(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        code="ENG",
        name="Engineering & Infrastructure",
        annual_budget=Decimal("1800000.00"),
    )
    dept_mkt = Department(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        code="MKT",
        name="Marketing & Growth",
        annual_budget=Decimal("950000.00"),
    )
    dept_fin = Department(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        code="FIN",
        name="Finance & Accounting",
        annual_budget=Decimal("600000.00"),
    )
    dept_hr = Department(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        code="HR",
        name="People Operations & HR",
        annual_budget=Decimal("400000.00"),
    )
    dept_sec = Department(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        code="SEC",
        name="Cybersecurity & Compliance",
        annual_budget=Decimal("750000.00"),
    )
    session.add_all([dept_eng, dept_mkt, dept_fin, dept_hr, dept_sec])
    await session.flush()

    # 2. Employees
    emp_alex = Employee(
        id=uuid.uuid4(),
        department_id=dept_eng.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-ENG-001",
        full_name="Alex Chen",
        email="alex.chen@enterprise.io",
        role_title="Principal Cloud Architect",
        employment_status="ACTIVE",
        hire_date=datetime.date(2022, 1, 15),
    )
    emp_sarah = Employee(
        id=uuid.uuid4(),
        department_id=dept_eng.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-ENG-002",
        full_name="Sarah Connor",
        email="sarah.connor@enterprise.io",
        role_title="Lead Data Engineer",
        employment_status="ACTIVE",
        hire_date=datetime.date(2022, 6, 10),
    )
    emp_david = Employee(
        id=uuid.uuid4(),
        department_id=dept_eng.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-ENG-003",
        full_name="David Miller",
        email="david.miller@enterprise.io",
        role_title="Senior Backend Developer",
        employment_status="ACTIVE",
        hire_date=datetime.date(2023, 3, 1),
    )
    emp_jessica = Employee(
        id=uuid.uuid4(),
        department_id=dept_mkt.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-MKT-001",
        full_name="Jessica Taylor",
        email="jessica.taylor@enterprise.io",
        role_title="VP of Growth",
        employment_status="ACTIVE",
        hire_date=datetime.date(2021, 11, 1),
    )
    emp_brian = Employee(
        id=uuid.uuid4(),
        department_id=dept_mkt.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-MKT-002",
        full_name="Brian Kim",
        email="brian.kim@enterprise.io",
        role_title="Product Marketing Manager",
        employment_status="ACTIVE",
        hire_date=datetime.date(2023, 8, 15),
    )
    emp_elena = Employee(
        id=uuid.uuid4(),
        department_id=dept_fin.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-FIN-001",
        full_name="Elena Rostova",
        email="elena.rostova@enterprise.io",
        role_title="Head of Financial Planning",
        employment_status="ACTIVE",
        hire_date=datetime.date(2020, 4, 12),
    )
    emp_marcus = Employee(
        id=uuid.uuid4(),
        department_id=dept_fin.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-FIN-002",
        full_name="Marcus Vance",
        email="marcus.vance@enterprise.io",
        role_title="Senior Financial Analyst",
        employment_status="ACTIVE",
        hire_date=datetime.date(2023, 1, 20),
    )
    emp_rachel = Employee(
        id=uuid.uuid4(),
        department_id=dept_hr.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-HR-001",
        full_name="Rachel Green",
        email="rachel.green@enterprise.io",
        role_title="Director of People Ops",
        employment_status="ACTIVE",
        hire_date=datetime.date(2021, 9, 1),
    )
    emp_daniel = Employee(
        id=uuid.uuid4(),
        department_id=dept_hr.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-HR-002",
        full_name="Daniel Craig",
        email="daniel.craig@enterprise.io",
        role_title="Talent Acquisition Lead",
        employment_status="ACTIVE",
        hire_date=datetime.date(2024, 2, 15),
    )
    emp_kavita = Employee(
        id=uuid.uuid4(),
        department_id=dept_sec.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-SEC-001",
        full_name="Kavita Rao",
        email="kavita.rao@enterprise.io",
        role_title="Chief Information Security Officer",
        employment_status="ACTIVE",
        hire_date=datetime.date(2021, 3, 1),
    )
    emp_tariq = Employee(
        id=uuid.uuid4(),
        department_id=dept_sec.id,
        tenant_id=TENANT_ID,
        employee_code="EMP-SEC-002",
        full_name="Tariq Mansoor",
        email="tariq.mansoor@enterprise.io",
        role_title="Compliance & Security Auditor",
        employment_status="ACTIVE",
        hire_date=datetime.date(2023, 10, 5),
    )
    session.add_all(
        [
            emp_alex,
            emp_sarah,
            emp_david,
            emp_jessica,
            emp_brian,
            emp_elena,
            emp_marcus,
            emp_rachel,
            emp_daniel,
            emp_kavita,
            emp_tariq,
        ]
    )
    await session.flush()

    # 3. Vendors
    vnd_cloud = Vendor(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        vendor_code="VND-CLD-001",
        name="CloudScale Systems",
        category="Software",
        risk_rating="LOW",
        is_active=True,
    )
    vnd_cyber = Vendor(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        vendor_code="VND-SEC-002",
        name="CyberFort Defense",
        category="Security",
        risk_rating="LOW",
        is_active=True,
    )
    vnd_data = Vendor(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        vendor_code="VND-DAT-003",
        name="DataFlow AI Analytics",
        category="Software",
        risk_rating="MEDIUM",
        is_active=True,
    )
    vnd_logistics = Vendor(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        vendor_code="VND-LOG-004",
        name="Apex Freight & Logistics",
        category="Logistics",
        risk_rating="MEDIUM",
        is_active=True,
    )
    vnd_beacon = Vendor(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        vendor_code="VND-CNS-005",
        name="Beacon Strategy Consulting",
        category="Consulting",
        risk_rating="HIGH",
        is_active=True,
    )
    vnd_supplies = Vendor(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        vendor_code="VND-OFC-006",
        name="OmniWorkspace Supplies",
        category="Supplies",
        risk_rating="LOW",
        is_active=False,  # Inactive vendor for status query demos
    )
    session.add_all([vnd_cloud, vnd_cyber, vnd_data, vnd_logistics, vnd_beacon, vnd_supplies])
    await session.flush()

    # 4. Contracts
    ctr_cloud = Contract(
        id=uuid.uuid4(),
        vendor_id=vnd_cloud.id,
        tenant_id=TENANT_ID,
        contract_number="CTR-2024-001",
        title="Enterprise Multi-Region Cloud Infrastructure Agreement",
        total_value=Decimal("320000.00"),
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2025, 12, 31),
        auto_renew=True,
        status="ACTIVE",
    )
    ctr_cyber = Contract(
        id=uuid.uuid4(),
        vendor_id=vnd_cyber.id,
        tenant_id=TENANT_ID,
        contract_number="CTR-2024-002",
        title="Annual Managed SOC & Penetration Testing Service Agreement",
        total_value=Decimal("140000.00"),
        start_date=datetime.date(2024, 6, 1),
        end_date=datetime.date(2025, 5, 31),
        auto_renew=False,
        status="ACTIVE",
    )
    ctr_data = Contract(
        id=uuid.uuid4(),
        vendor_id=vnd_data.id,
        tenant_id=TENANT_ID,
        contract_number="CTR-2024-003",
        title="Real-time Stream Processing & ML Feature Store License",
        total_value=Decimal("90000.00"),
        start_date=datetime.date(2024, 3, 15),
        end_date=datetime.date(2025, 3, 14),
        auto_renew=True,
        status="EXPIRED",
    )
    ctr_logistics = Contract(
        id=uuid.uuid4(),
        vendor_id=vnd_logistics.id,
        tenant_id=TENANT_ID,
        contract_number="CTR-2025-004",
        title="Global Freight Forwarding and Warehousing Master Agreement",
        total_value=Decimal("185000.00"),
        start_date=datetime.date(2025, 1, 1),
        end_date=datetime.date(2025, 12, 31),
        auto_renew=False,
        status="ACTIVE",
    )
    ctr_beacon = Contract(
        id=uuid.uuid4(),
        vendor_id=vnd_beacon.id,
        tenant_id=TENANT_ID,
        contract_number="CTR-2024-005",
        title="Enterprise Digital Transformation and Cloud Architecture Advisory",
        total_value=Decimal("75000.00"),
        start_date=datetime.date(2024, 9, 1),
        end_date=datetime.date(2025, 8, 31),
        auto_renew=False,
        status="ACTIVE",
    )
    session.add_all([ctr_cloud, ctr_cyber, ctr_data, ctr_logistics, ctr_beacon])
    await session.flush()

    # 5. Invoices
    # CloudScale: 4 invoices ($80k each = $320k, fully matches contract)
    inv_cld_1 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_cloud.id,
        contract_id=ctr_cloud.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-CLD-101",
        amount=Decimal("80000.00"),
        issue_date=datetime.date(2024, 3, 31),
        due_date=datetime.date(2024, 4, 30),
        payment_status="PAID",
        paid_at=datetime.datetime(2024, 4, 25, 14, 0, tzinfo=datetime.UTC),
    )
    inv_cld_2 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_cloud.id,
        contract_id=ctr_cloud.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-CLD-102",
        amount=Decimal("80000.00"),
        issue_date=datetime.date(2024, 6, 30),
        due_date=datetime.date(2024, 7, 31),
        payment_status="PAID",
        paid_at=datetime.datetime(2024, 7, 28, 10, 30, tzinfo=datetime.UTC),
    )
    inv_cld_3 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_cloud.id,
        contract_id=ctr_cloud.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-CLD-103",
        amount=Decimal("80000.00"),
        issue_date=datetime.date(2024, 9, 30),
        due_date=datetime.date(2024, 10, 31),
        payment_status="PAID",
        paid_at=datetime.datetime(2024, 10, 29, 16, 15, tzinfo=datetime.UTC),
    )
    inv_cld_4 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_cloud.id,
        contract_id=ctr_cloud.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-CLD-104",
        amount=Decimal("80000.00"),
        issue_date=datetime.date(2024, 12, 31),
        due_date=datetime.date(2025, 1, 31),
        payment_status="PENDING",
        paid_at=None,
    )

    # CyberFort: $140k total ($70k paid, $70k overdue)
    inv_sec_1 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_cyber.id,
        contract_id=ctr_cyber.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-SEC-201",
        amount=Decimal("70000.00"),
        issue_date=datetime.date(2024, 6, 15),
        due_date=datetime.date(2024, 7, 15),
        payment_status="PAID",
        paid_at=datetime.datetime(2024, 7, 10, 11, 0, tzinfo=datetime.UTC),
    )
    inv_sec_2 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_cyber.id,
        contract_id=ctr_cyber.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-SEC-202",
        amount=Decimal("70000.00"),
        issue_date=datetime.date(2024, 12, 15),
        due_date=datetime.date(2025, 1, 15),
        payment_status="OVERDUE",
        paid_at=None,
    )

    # Beacon Consulting: Contract is $75,000, but billed $85,000 (EXCEEDS contract value by $10k!)
    inv_cns_1 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_beacon.id,
        contract_id=ctr_beacon.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-CNS-301",
        amount=Decimal("45000.00"),
        issue_date=datetime.date(2024, 10, 1),
        due_date=datetime.date(2024, 10, 31),
        payment_status="PAID",
        paid_at=datetime.datetime(2024, 10, 25, 9, 30, tzinfo=datetime.UTC),
    )
    inv_cns_2 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_beacon.id,
        contract_id=ctr_beacon.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-CNS-302",
        amount=Decimal("40000.00"),
        issue_date=datetime.date(2024, 12, 1),
        due_date=datetime.date(2024, 12, 31),
        payment_status="PENDING",
        paid_at=None,
    )

    # Apex Logistics: $35k paid, $42.5k pending
    inv_log_1 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_logistics.id,
        contract_id=ctr_logistics.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-LOG-401",
        amount=Decimal("35000.00"),
        issue_date=datetime.date(2025, 1, 15),
        due_date=datetime.date(2025, 2, 15),
        payment_status="PAID",
        paid_at=datetime.datetime(2025, 2, 10, 15, 45, tzinfo=datetime.UTC),
    )
    inv_log_2 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_logistics.id,
        contract_id=ctr_logistics.id,
        tenant_id=TENANT_ID,
        invoice_number="INV-LOG-402",
        amount=Decimal("42500.00"),
        issue_date=datetime.date(2025, 2, 15),
        due_date=datetime.date(2025, 3, 15),
        payment_status="PENDING",
        paid_at=None,
    )

    # OmniWorkspace: Ad-hoc supply invoice without formal contract
    inv_ofc_1 = Invoice(
        id=uuid.uuid4(),
        vendor_id=vnd_supplies.id,
        contract_id=None,
        tenant_id=TENANT_ID,
        invoice_number="INV-OFC-501",
        amount=Decimal("6200.00"),
        issue_date=datetime.date(2025, 1, 10),
        due_date=datetime.date(2025, 2, 10),
        payment_status="PAID",
        paid_at=datetime.datetime(2025, 2, 5, 12, 0, tzinfo=datetime.UTC),
    )

    session.add_all(
        [
            inv_cld_1,
            inv_cld_2,
            inv_cld_3,
            inv_cld_4,
            inv_sec_1,
            inv_sec_2,
            inv_cns_1,
            inv_cns_2,
            inv_log_1,
            inv_log_2,
            inv_ofc_1,
        ]
    )
    await session.flush()

    # 6. Operational Expenses
    expenses = [
        # Engineering expenses
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_eng.id,
            employee_id=emp_alex.id,
            tenant_id=TENANT_ID,
            category="Software",
            amount=Decimal("14200.00"),
            currency="USD",
            expense_date=datetime.date(2025, 1, 15),
            description="Annual GitHub Enterprise and Datadog monitoring tier licenses",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_eng.id,
            employee_id=emp_alex.id,
            tenant_id=TENANT_ID,
            category="Travel",
            amount=Decimal("3450.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 10),
            description="AWS re:Invent conference registration and round-trip flights",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_eng.id,
            employee_id=emp_sarah.id,
            tenant_id=TENANT_ID,
            category="Software",
            amount=Decimal("8900.00"),
            currency="USD",
            expense_date=datetime.date(2025, 1, 22),
            description="Snowflake analytics credits and dbt Cloud team seat renewal",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_eng.id,
            employee_id=emp_sarah.id,
            tenant_id=TENANT_ID,
            category="Supplies",
            amount=Decimal("780.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 5),
            description="Developer dual-4K monitor workstation arm and docking station",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_eng.id,
            employee_id=emp_david.id,
            tenant_id=TENANT_ID,
            category="Supplies",
            amount=Decimal("1250.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 18),
            description="Hardware testing peripherals and IoT microcontroller kits",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_eng.id,
            employee_id=emp_david.id,
            tenant_id=TENANT_ID,
            category="Meals",
            amount=Decimal("450.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 28),
            description="Engineering sprint retrospective team dinner",
            approved=True,
        ),
        # Marketing expenses
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_mkt.id,
            employee_id=emp_jessica.id,
            tenant_id=TENANT_ID,
            category="Software",
            amount=Decimal("18500.00"),
            currency="USD",
            expense_date=datetime.date(2025, 1, 5),
            description="HubSpot Marketing Hub & Salesforce CRM quarterly seat renewal",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_mkt.id,
            employee_id=emp_jessica.id,
            tenant_id=TENANT_ID,
            category="Travel",
            amount=Decimal("6200.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 14),
            description="SaaStr Annual conference sponsorship booth and team travel",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_mkt.id,
            employee_id=emp_brian.id,
            tenant_id=TENANT_ID,
            category="Consulting",
            amount=Decimal("4800.00"),
            currency="USD",
            expense_date=datetime.date(2025, 1, 30),
            description="SEO & organic content strategy audit with external agency",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_mkt.id,
            employee_id=emp_brian.id,
            tenant_id=TENANT_ID,
            category="Meals",
            amount=Decimal("620.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 12),
            description="Enterprise prospect executive briefing lunch",
            approved=False,  # Unapproved expense for filter testing
        ),
        # Finance expenses
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_fin.id,
            employee_id=emp_elena.id,
            tenant_id=TENANT_ID,
            category="Software",
            amount=Decimal("12000.00"),
            currency="USD",
            expense_date=datetime.date(2025, 1, 10),
            description="NetSuite ERP cloud subscription & financial reporting module",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_fin.id,
            employee_id=emp_marcus.id,
            tenant_id=TENANT_ID,
            category="Travel",
            amount=Decimal("2800.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 20),
            description="Internal audit on-site review at regional logistics distribution hub",
            approved=True,
        ),
        # Cybersecurity expenses
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_sec.id,
            employee_id=emp_kavita.id,
            tenant_id=TENANT_ID,
            category="Software",
            amount=Decimal("22500.00"),
            currency="USD",
            expense_date=datetime.date(2025, 1, 8),
            description="CrowdStrike Falcon EDR and Wiz Cloud Security posture licenses",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_sec.id,
            employee_id=emp_kavita.id,
            tenant_id=TENANT_ID,
            category="Travel",
            amount=Decimal("4100.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 15),
            description="RSA Security Conference keynote attendance and travel",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_sec.id,
            employee_id=emp_tariq.id,
            tenant_id=TENANT_ID,
            category="Consulting",
            amount=Decimal("5500.00"),
            currency="USD",
            expense_date=datetime.date(2025, 1, 25),
            description="SOC2 Type II external compliance readiness assessment",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_sec.id,
            employee_id=emp_tariq.id,
            tenant_id=TENANT_ID,
            category="Supplies",
            amount=Decimal("1800.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 2),
            description="Encrypted YubiKey hardware security tokens for employee MFA",
            approved=True,
        ),
        # Human Resources expenses
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_hr.id,
            employee_id=emp_rachel.id,
            tenant_id=TENANT_ID,
            category="Software",
            amount=Decimal("7500.00"),
            currency="USD",
            expense_date=datetime.date(2025, 1, 12),
            description="Workday HCM and Greenhouse ATS recruiter subscriptions",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_hr.id,
            employee_id=emp_daniel.id,
            tenant_id=TENANT_ID,
            category="Travel",
            amount=Decimal("3200.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 8),
            description="University campus recruitment tour, flight and lodging",
            approved=True,
        ),
        OperationalExpense(
            id=uuid.uuid4(),
            department_id=dept_hr.id,
            employee_id=emp_daniel.id,
            tenant_id=TENANT_ID,
            category="Meals",
            amount=Decimal("850.00"),
            currency="USD",
            expense_date=datetime.date(2025, 2, 19),
            description="New hire quarterly orientation and welcome catering",
            approved=True,
        ),
    ]
    session.add_all(expenses)
    await session.flush()

    return {
        "departments": 5,
        "employees": 11,
        "vendors": 6,
        "contracts": 5,
        "invoices": 11,
        "operational_expenses": len(expenses),
    }


async def main() -> None:
    logger.info("==================================================")
    logger.info("Starting Enterprise DB Seeding for Text-to-SQL...")
    logger.info("==================================================")

    async with AsyncSessionLocal() as session:
        try:
            # 1. Seed / verify Admin User
            await seed_admin_user(session)

            # 2. Reset and seed operational tables
            await clear_operational_data(session)
            counts = await seed_operational_entities(session)

            # 3. Commit transaction
            await session.commit()

            logger.info("==================================================")
            logger.info("Seeding completed successfully! ✅")
            logger.info("--------------------------------------------------")
            logger.info("Admin Credentials:")
            logger.info("  Email:    %s", ADMIN_EMAIL)
            logger.info("  Password: %s", ADMIN_PASSWORD)
            logger.info("  Role:     ADMIN")
            logger.info("  Tenant:   %s", TENANT_ID)
            logger.info("--------------------------------------------------")
            logger.info("Operational Entities Seeded:")
            for entity, count in counts.items():
                logger.info(f"  - {entity.capitalize()}: {count} records")
            logger.info("==================================================")

        except Exception as e:
            await session.rollback()
            logger.error("Seeding failed: %s", e, exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
