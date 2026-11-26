from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utc_now():
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    fictional_demo_flag: Mapped[bool] = mapped_column(Boolean, default=True)


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    display_name: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_services: Mapped[str] = mapped_column(String, default="stock,pension,wellness,custody,equity")


class McpSetting(Base):
    __tablename__ = "mcp_settings"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    changed_by: Mapped[str] = mapped_column(String)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reason: Mapped[str] = mapped_column(String, default="Initial demo setting")


class TenantServiceSetting(Base):
    __tablename__ = "tenant_service_settings"
    __table_args__ = (UniqueConstraint("tenant_id", "service"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service: Mapped[str] = mapped_column(String, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    changed_by: Mapped[str] = mapped_column(String)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reason: Mapped[str] = mapped_column(String, default="Initial demo setting")


class AccessChange(Base):
    __tablename__ = "access_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String, index=True)
    actor: Mapped[str] = mapped_column(String)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service: Mapped[str] = mapped_column(String)  # "master" or one of catalog.SERVICES
    previous_enabled: Mapped[bool] = mapped_column(Boolean)
    new_enabled: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class StockAccount(Base):
    __tablename__ = "stock_accounts"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String)
    opening_shares: Mapped[int] = mapped_column(Integer, default=0)
    monthly_contribution_jpy: Mapped[int] = mapped_column(Integer)


class StockPlanDetail(Base):
    __tablename__ = "stock_plan_details"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    plan_name: Mapped[str] = mapped_column(String)
    enrollment_date: Mapped[date] = mapped_column(Date)
    participation_status: Mapped[str] = mapped_column(String)
    opening_cost_jpy: Mapped[int] = mapped_column(Integer)
    employer_incentive_percent: Mapped[int] = mapped_column(Integer)
    illustrative_price_jpy: Mapped[float] = mapped_column(Numeric(18, 4))


class StockIncentive(Base):
    __tablename__ = "stock_incentives"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    month: Mapped[date] = mapped_column(Date)
    amount_jpy: Mapped[int] = mapped_column(Integer)


class PayrollContribution(Base):
    __tablename__ = "payroll_contributions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    month: Mapped[date] = mapped_column(Date)
    amount_jpy: Mapped[int] = mapped_column(Integer)


class SharePurchase(Base):
    __tablename__ = "share_purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    purchase_date: Mapped[date] = mapped_column(Date)
    shares: Mapped[int] = mapped_column(Integer)
    price_jpy: Mapped[int] = mapped_column(Integer)
    amount_jpy: Mapped[int] = mapped_column(Integer)


class PensionAccount(Base):
    __tablename__ = "pension_accounts"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    account_type: Mapped[str] = mapped_column(String)
    opening_balance_jpy: Mapped[int] = mapped_column(Integer)
    investment_change_jpy: Mapped[int] = mapped_column(Integer)


class PensionContribution(Base):
    __tablename__ = "pension_contributions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    contribution_date: Mapped[date] = mapped_column(Date)
    employee_amount_jpy: Mapped[int] = mapped_column(Integer)
    employer_amount_jpy: Mapped[int] = mapped_column(Integer)


class PensionAllocation(Base):
    __tablename__ = "pension_allocations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    asset_class: Mapped[str] = mapped_column(String)
    percentage: Mapped[int] = mapped_column(Integer)


class PensionValuation(Base):
    __tablename__ = "pension_valuations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    valuation_date: Mapped[date] = mapped_column(Date)
    balance_jpy: Mapped[int] = mapped_column(Integer)
    illustrative_nav: Mapped[float] = mapped_column(Numeric(18, 4))


class WellnessProgress(Base):
    __tablename__ = "wellness_progress"
    __table_args__ = (UniqueConstraint("employee_id", "resource_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("wellness_resources.id"))
    status: Mapped[str] = mapped_column(String)


class WellnessPreference(Base):
    __tablename__ = "wellness_preferences"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    topic: Mapped[str] = mapped_column(String)


class WellnessResource(Base):
    __tablename__ = "wellness_resources"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    topic: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)


class CustodyPosition(Base):
    __tablename__ = "custody_positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    instrument: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer)


class CustodyAccount(Base):
    __tablename__ = "custody_accounts"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    account_id: Mapped[str] = mapped_column(String)
    opened_on: Mapped[date] = mapped_column(Date)
    account_status: Mapped[str] = mapped_column(String)


class CustodySecurity(Base):
    __tablename__ = "custody_securities"
    instrument: Mapped[str] = mapped_column(String, primary_key=True)
    security_id: Mapped[str] = mapped_column(String)
    asset_class: Mapped[str] = mapped_column(String)
    illustrative_price_jpy: Mapped[float] = mapped_column(Numeric(18, 4))


class CustodySettlement(Base):
    __tablename__ = "custody_settlements"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    instrument: Mapped[str] = mapped_column(String)
    trade_date: Mapped[date] = mapped_column(Date)
    settlement_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)


class CustodyValuation(Base):
    __tablename__ = "custody_valuations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    valuation_date: Mapped[date] = mapped_column(Date)
    illustrative_value_jpy: Mapped[int] = mapped_column(Integer)


class DividendDetail(Base):
    __tablename__ = "dividend_details"
    dividend_id: Mapped[int] = mapped_column(ForeignKey("dividends.id"), primary_key=True)
    record_date: Mapped[date] = mapped_column(Date)


class Dividend(Base):
    __tablename__ = "dividends"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    payment_date: Mapped[date] = mapped_column(Date)
    instrument: Mapped[str] = mapped_column(String)
    amount_jpy: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)


class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    effective_date: Mapped[date] = mapped_column(Date)


class CorporateActionDetail(Base):
    __tablename__ = "corporate_action_details"
    action_id: Mapped[str] = mapped_column(ForeignKey("corporate_actions.id"), primary_key=True)
    record_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)


class EquityGrant(Base):
    __tablename__ = "equity_grants"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    award_type: Mapped[str] = mapped_column(String)
    granted_units: Mapped[int] = mapped_column(Integer)
    grant_date: Mapped[date] = mapped_column(Date)


class EquityGrantDetail(Base):
    __tablename__ = "equity_grant_details"
    grant_id: Mapped[str] = mapped_column(ForeignKey("equity_grants.id"), primary_key=True)
    plan_name: Mapped[str] = mapped_column(String)
    vesting_condition: Mapped[str] = mapped_column(String)
    exercise_price_jpy: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    forfeited_units: Mapped[int] = mapped_column(Integer, default=0)
    released_units: Mapped[int] = mapped_column(Integer, default=0)
    exercised_units: Mapped[int] = mapped_column(Integer, default=0)
    illustrative_share_price_jpy: Mapped[float] = mapped_column(Numeric(18, 4))


class VestingEvent(Base):
    __tablename__ = "vesting_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grant_id: Mapped[str] = mapped_column(ForeignKey("equity_grants.id"), index=True)
    vest_date: Mapped[date] = mapped_column(Date)
    units: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String, index=True)
    actor: Mapped[str] = mapped_column(String)
    tenant_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    employee_id: Mapped[str | None] = mapped_column(String, nullable=True)
    service: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
