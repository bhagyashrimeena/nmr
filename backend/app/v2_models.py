"""Normalized operational records for the versioned workplace finance API."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import utc_now


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LegalEntity(Base):
    __tablename__ = "legal_entities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String)


class TenantOperationalStatus(Base):
    __tablename__ = "tenant_operational_status"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String)


class ClientServiceAgreement(Base):
    __tablename__ = "client_service_agreements"
    __table_args__ = (UniqueConstraint("tenant_id", "service"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    service: Mapped[str] = mapped_column(String)
    effective_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)
    source_reference: Mapped[str] = mapped_column(String)


class ParticipantOperationalProfile(Base):
    __tablename__ = "participant_operational_profiles"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    department: Mapped[str] = mapped_column(String)
    cohort: Mapped[str] = mapped_column(String)
    hired_on: Mapped[date] = mapped_column(Date)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    hired_on: Mapped[date] = mapped_column(Date)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_status: Mapped[str] = mapped_column(String)


class FinancialEvent(Base):
    __tablename__ = "financial_events"
    __table_args__ = (UniqueConstraint("tenant_id", "service", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    service: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String)
    source_reference: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    amount_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String, default="JPY")
    actor: Mapped[str] = mapped_column(String)


@event.listens_for(FinancialEvent, "before_update")
@event.listens_for(FinancialEvent, "before_delete")
def reject_financial_event_mutation(_mapper, _connection, _target):
    raise ValueError("Financial events are append-only; post a correction event instead.")


class OperationAudit(Base):
    __tablename__ = "operation_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    employee_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor: Mapped[str] = mapped_column(String)
    principal_scopes: Mapped[str] = mapped_column(String)
    service: Mapped[str] = mapped_column(String)
    operation: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReconciliationCase(Base):
    __tablename__ = "reconciliation_cases"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service: Mapped[str] = mapped_column(String, index=True)
    employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    source_reference: Mapped[str] = mapped_column(String)
    break_type: Mapped[str] = mapped_column(String)
    expected_jpy: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    actual_jpy: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(String)
    owner: Mapped[str] = mapped_column(String)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CaseResolution(Base):
    __tablename__ = "case_resolutions"
    case_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_cases.id"), primary_key=True)
    action: Mapped[str] = mapped_column(String)
    evidence_reference: Mapped[str] = mapped_column(String)
    related_batch_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service: Mapped[str] = mapped_column(String, index=True)
    employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    operation_key: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    reviewer_role: Mapped[str] = mapped_column(String)
    evidence_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("workflow_tasks.id"), index=True)
    from_state: Mapped[str | None] = mapped_column(String, nullable=True)
    to_state: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OperationalStatement(Base):
    __tablename__ = "operational_statements"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    service: Mapped[str] = mapped_column(String, index=True)
    period: Mapped[str] = mapped_column(String)
    as_of: Mapped[date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer)
    source_reference: Mapped[str] = mapped_column(String)


class EquityPlanV2(Base):
    __tablename__ = "equity_plans_v2"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    authorized_units: Mapped[int] = mapped_column(Integer)
    acceptance_required: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String)


class EquityAward(Base):
    __tablename__ = "equity_awards_v2"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("equity_plans_v2.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    award_type: Mapped[str] = mapped_column(String)
    granted_units: Mapped[int] = mapped_column(Integer)
    grant_date: Mapped[date] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String)
    strike_jpy: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    released_units: Mapped[int] = mapped_column(Integer, default=0)
    exercised_units: Mapped[int] = mapped_column(Integer, default=0)
    forfeited_units: Mapped[int] = mapped_column(Integer, default=0)


class EquityTranche(Base):
    __tablename__ = "equity_tranches_v2"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    award_id: Mapped[str] = mapped_column(ForeignKey("equity_awards_v2.id"), index=True)
    vest_date: Mapped[date] = mapped_column(Date)
    units: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String)


class EquityRelease(Base):
    __tablename__ = "equity_releases_v2"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    award_id: Mapped[str] = mapped_column(ForeignKey("equity_awards_v2.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    units: Mapped[int] = mapped_column(Integer)
    withholding_units: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String)
    custody_confirmation: Mapped[str | None] = mapped_column(String, nullable=True)


class EquityExerciseDraft(Base):
    __tablename__ = "equity_exercise_drafts_v2"
    __table_args__ = (UniqueConstraint("employee_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    award_id: Mapped[str] = mapped_column(ForeignKey("equity_awards_v2.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    units: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CustodyAccountV2(Base):
    __tablename__ = "custody_accounts_v2"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String)
    security_id: Mapped[str] = mapped_column(String)
    instrument: Mapped[str] = mapped_column(String)


class CustodyDividendV2(Base):
    __tablename__ = "custody_dividends_v2"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("custody_accounts_v2.id"), index=True)
    record_date: Mapped[date] = mapped_column(Date)
    payment_date: Mapped[date] = mapped_column(Date)
    entitlement_units: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    amount_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    state: Mapped[str] = mapped_column(String)


class CustodyActionV2(Base):
    __tablename__ = "custody_actions_v2"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("custody_accounts_v2.id"), index=True)
    action_type: Mapped[str] = mapped_column(String)
    record_date: Mapped[date] = mapped_column(Date)
    effective_date: Mapped[date] = mapped_column(Date)
    numerator: Mapped[int] = mapped_column(Integer)
    denominator: Mapped[int] = mapped_column(Integer)
    eligible_units: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    added_units: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    state: Mapped[str] = mapped_column(String)


class WellnessContentV2(Base):
    __tablename__ = "wellness_content_v2"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    language: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String)
    source_reference: Mapped[str] = mapped_column(String)
    effective_date: Mapped[date] = mapped_column(Date)
    review_expires_on: Mapped[date] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer)


class WellnessBenefitRule(Base):
    __tablename__ = "wellness_benefit_rules"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    benefit_key: Mapped[str] = mapped_column(String)
    rule_text: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[str] = mapped_column(String)
    effective_date: Mapped[date] = mapped_column(Date)
    review_expires_on: Mapped[date] = mapped_column(Date)


class WellnessBenefitAccess(Base):
    __tablename__ = "wellness_benefit_access"
    rule_id: Mapped[str] = mapped_column(ForeignKey("wellness_benefit_rules.id"), primary_key=True)
    underlying_service: Mapped[str] = mapped_column(String)


class WellnessSeminar(Base):
    __tablename__ = "wellness_seminars"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    registrations: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)


class ShareholdingPlan(Base):
    __tablename__ = "shareholding_plans"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    name: Mapped[str] = mapped_column(String)
    issuer: Mapped[str] = mapped_column(String)
    minimum_monthly_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    maximum_monthly_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    incentive_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    fractional_units_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    minimum_transfer_units: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    next_purchase_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)


class ShareholdingRuleVersion(Base):
    __tablename__ = "shareholding_rule_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("shareholding_plans.id"), index=True)
    effective_on: Mapped[date] = mapped_column(Date)
    source_reference: Mapped[str] = mapped_column(String)
    incentive_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    minimum_transfer_units: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    fractional_beneficial_units: Mapped[bool] = mapped_column(Boolean)


class ShareMembership(Base):
    __tablename__ = "share_memberships"
    __table_args__ = (UniqueConstraint("plan_id", "employee_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("shareholding_plans.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    joined_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)
    opening_units: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    opening_cash_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))


class ContributionElection(Base):
    __tablename__ = "contribution_elections"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    membership_id: Mapped[str] = mapped_column(ForeignKey("share_memberships.id"), index=True)
    monthly_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    effective_period: Mapped[date] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String)


class SharePayrollBatch(Base):
    __tablename__ = "share_payroll_batches"
    __table_args__ = (UniqueConstraint("plan_id", "period", "source_reference"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("shareholding_plans.id"), index=True)
    period: Mapped[date] = mapped_column(Date)
    source_reference: Mapped[str] = mapped_column(String)
    expected_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    received_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    state: Mapped[str] = mapped_column(String)


class SharePayrollRuleLink(Base):
    __tablename__ = "share_payroll_rule_links"
    batch_id: Mapped[str] = mapped_column(ForeignKey("share_payroll_batches.id"), primary_key=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("shareholding_rule_versions.id"))


class SharePayrollLine(Base):
    __tablename__ = "share_payroll_lines"
    __table_args__ = (UniqueConstraint("batch_id", "employee_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("share_payroll_batches.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    amount_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    incentive_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    state: Mapped[str] = mapped_column(String)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class SharePurchaseCycle(Base):
    __tablename__ = "share_purchase_cycles"
    __table_args__ = (UniqueConstraint("plan_id", "source_reference"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("shareholding_plans.id"), index=True)
    source_reference: Mapped[str] = mapped_column(String)
    trade_date: Mapped[date] = mapped_column(Date)
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    unit_price_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    acquired_units: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    state: Mapped[str] = mapped_column(String)


class SharePurchaseAllocation(Base):
    __tablename__ = "share_purchase_allocations"
    __table_args__ = (UniqueConstraint("cycle_id", "employee_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[str] = mapped_column(ForeignKey("share_purchase_cycles.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    units: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    cost_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    state: Mapped[str] = mapped_column(String)


class ShareTransferRequest(Base):
    __tablename__ = "share_transfer_requests"
    __table_args__ = (UniqueConstraint("tenant_id", "employee_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("shareholding_plans.id"))
    units: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    recipient_account_reference: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String)
    correlation_id: Mapped[str] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CustodySettlementConfirmation(Base):
    __tablename__ = "custody_settlement_confirmations"
    transfer_id: Mapped[str] = mapped_column(ForeignKey("share_transfer_requests.id"), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("custody_accounts_v2.id"), index=True)
    confirmation_reference: Mapped[str] = mapped_column(String, unique=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String)


class PensionPlanV2(Base):
    __tablename__ = "pension_plans_v2"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    effective_on: Mapped[date] = mapped_column(Date)


class PensionFund(Base):
    __tablename__ = "pension_funds"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("pension_plans_v2.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    annual_fee_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    eligible: Mapped[bool] = mapped_column(Boolean)


class PensionNav(Base):
    __tablename__ = "pension_nav"
    __table_args__ = (UniqueConstraint("fund_id", "valuation_date"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    fund_id: Mapped[str] = mapped_column(ForeignKey("pension_funds.id"), index=True)
    valuation_date: Mapped[date] = mapped_column(Date)
    nav_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 4))


class PensionFundPosition(Base):
    __tablename__ = "pension_fund_positions"
    __table_args__ = (UniqueConstraint("employee_id", "fund_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    fund_id: Mapped[str] = mapped_column(ForeignKey("pension_funds.id"))
    units: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    as_of: Mapped[date] = mapped_column(Date)


class PensionFutureAllocation(Base):
    __tablename__ = "pension_future_allocations"
    __table_args__ = (UniqueConstraint("employee_id", "fund_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    fund_id: Mapped[str] = mapped_column(ForeignKey("pension_funds.id"))
    percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    effective_period: Mapped[date] = mapped_column(Date)


class PensionSwitchDraft(Base):
    __tablename__ = "pension_switch_drafts"
    __table_args__ = (UniqueConstraint("tenant_id", "employee_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    from_fund_id: Mapped[str] = mapped_column(ForeignKey("pension_funds.id"))
    to_fund_id: Mapped[str] = mapped_column(ForeignKey("pension_funds.id"))
    units: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    idempotency_key: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PensionContributionRecord(Base):
    __tablename__ = "pension_contribution_records"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    source_reference: Mapped[str] = mapped_column(String)
    period: Mapped[date] = mapped_column(Date)
    employee_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    employer_jpy: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    state: Mapped[str] = mapped_column(String)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class PensionAllocationInstruction(Base):
    __tablename__ = "pension_allocation_instructions"
    __table_args__ = (UniqueConstraint("tenant_id", "employee_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    state: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PensionInstructionLine(Base):
    __tablename__ = "pension_instruction_lines"
    __table_args__ = (UniqueConstraint("instruction_id", "fund_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    instruction_id: Mapped[str] = mapped_column(ForeignKey("pension_allocation_instructions.id"), index=True)
    fund_id: Mapped[str] = mapped_column(ForeignKey("pension_funds.id"))
    percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4))

