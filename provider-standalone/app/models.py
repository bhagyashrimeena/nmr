from datetime import datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, JSON, Boolean, DateTime, UniqueConstraint, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def now():
    return datetime.now(timezone.utc)

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    fictional: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mcp_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_by: Mapped[str] = mapped_column(String(120), default="seed")

class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(80))
    job_title: Mapped[str] = mapped_column(String(80))
    joined_on: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")

class ServicePermission(Base):
    __tablename__ = "service_permissions"
    __table_args__ = (UniqueConstraint("tenant_id", "service_key", name="tenant_service_unique"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service_key: Mapped[str] = mapped_column(String(60))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_by: Mapped[str] = mapped_column(String(120), default="seed")

class EmployeeService(Base):
    __tablename__ = "employee_services"
    __table_args__ = (UniqueConstraint("employee_id", "service_key", name="employee_service_unique"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    service_key: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

class WellnessResource(Base):
    __tablename__ = "wellness_resources"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    topic: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    reading_minutes: Mapped[int] = mapped_column(Integer, default=4)
    level: Mapped[str] = mapped_column(String(32), default="Foundations")

class WellnessProgress(Base):
    __tablename__ = "wellness_progress"
    __table_args__ = (UniqueConstraint("employee_id", "resource_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("wellness_resources.id"))
    status: Mapped[str] = mapped_column(String(32), default="not_started")

class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("audit_tenant_time", "tenant_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(120))
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    employee_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(120))
    service_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    outcome: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
