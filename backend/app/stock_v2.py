"""Shareholding operations backed by dated, immutable journal entries."""
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Employee, Tenant
from .security import ApiError, audit, require_admin, require_client
from .v2_models import (
    ContributionElection, CustodyAccountV2, CustodySettlementConfirmation, FinancialEvent,
    OperationalStatement, ReconciliationCase,
    ShareMembership, SharePayrollBatch, SharePayrollLine, SharePayrollRuleLink,
    SharePurchaseAllocation, SharePurchaseCycle, ShareTransferRequest, ShareholdingPlan,
    ShareholdingRuleVersion, WorkflowTask, WorkflowTransition,
)
from .v2_seed import SNAPSHOT, at_day

router = APIRouter(prefix="/api/v2", tags=["Shareholding operations"])


def money(value):
    return f"{Decimal(value):.2f}"


def units(value):
    return f"{Decimal(value):.6f}"


def tenant_plan(db: Session, tenant_id: str):
    if not db.get(Tenant, tenant_id):
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Corporate client is not available.")
    plan = db.scalar(select(ShareholdingPlan).where(ShareholdingPlan.tenant_id == tenant_id))
    if not plan:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Shareholding plan is not available.")
    return plan


def membership(db: Session, tenant_id: str, employee_id: str):
    plan = tenant_plan(db, tenant_id)
    row = db.scalar(select(ShareMembership).where(ShareMembership.plan_id == plan.id,
                                                  ShareMembership.employee_id == employee_id))
    if not row:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Shareholding membership is not available.")
    return plan, row


def rule_for_period(db: Session, plan_id: str, period: date):
    rule = db.scalar(select(ShareholdingRuleVersion).where(
        ShareholdingRuleVersion.plan_id == plan_id,
        ShareholdingRuleVersion.effective_on <= period).order_by(ShareholdingRuleVersion.effective_on.desc()))
    if not rule:
        raise ApiError(422, "PLAN_RULE_NOT_AVAILABLE", "No effective shareholding rule is available for this period.")
    return rule


def journal(db: Session, tenant_id: str, employee_id: str, service: str = "stock"):
    return db.scalars(select(FinancialEvent).where(FinancialEvent.tenant_id == tenant_id,
                                                    FinancialEvent.employee_id == employee_id,
                                                    FinancialEvent.service == service)
                      .order_by(FinancialEvent.effective_at, FinancialEvent.id)).all()


def ledger_row(row: FinancialEvent):
    return {"id": row.id, "event_type": row.event_type, "source_reference": row.source_reference,
            "correlation_id": row.correlation_id, "occurred_at": row.occurred_at,
            "effective_at": row.effective_at, "recorded_at": row.recorded_at,
            "amount_jpy": money(row.amount_jpy), "quantity": units(row.quantity), "currency": row.currency}


def balances(db: Session, tenant_id: str, employee_id: str):
    events = journal(db, tenant_id, employee_id)
    cash = sum((Decimal(event.amount_jpy) for event in events), Decimal("0"))
    shares = sum((Decimal(event.quantity) for event in events), Decimal("0"))
    if cash < 0 or shares < 0:
        raise ApiError(409, "RECONCILIATION_FAILED", "Shareholding balance does not reconcile.")
    return shares, cash


def transfer_row(row: ShareTransferRequest):
    return {"request_id": row.id, "employee_id": row.employee_id, "plan_id": row.plan_id,
            "units": units(row.units), "recipient_account_reference": row.recipient_account_reference,
            "state": row.state, "correlation_id": row.correlation_id, "submitted_at": row.submitted_at}


def eligible_recipient(db: Session, tenant_id: str, employee_id: str, reference: str,
                       plan: ShareholdingPlan):
    account = db.get(CustodyAccountV2, reference)
    if (not account or account.tenant_id != tenant_id or account.employee_id != employee_id
            or account.status != "ACTIVE" or plan.issuer not in account.instrument):
        raise ApiError(422, "RECIPIENT_ACCOUNT_NOT_ELIGIBLE",
                       "A matching active securities account is required for this transfer.")
    return account


def stock_summary(db: Session, tenant_id: str, employee_id: str):
    plan, member = membership(db, tenant_id, employee_id)
    rule = rule_for_period(db, plan.id, SNAPSHOT.date())
    shares, cash = balances(db, tenant_id, employee_id)
    posted_cash = db.scalar(select(func.sum(SharePayrollLine.amount_jpy))
                            .join(SharePayrollBatch, SharePayrollBatch.id == SharePayrollLine.batch_id)
                            .where(SharePayrollLine.employee_id == employee_id, SharePayrollLine.state == "POSTED"))
    incentives = db.scalar(select(func.sum(SharePayrollLine.incentive_jpy))
                           .join(SharePayrollBatch, SharePayrollBatch.id == SharePayrollLine.batch_id)
                           .where(SharePayrollLine.employee_id == employee_id, SharePayrollLine.state == "POSTED"))
    allocations = db.scalars(select(SharePurchaseAllocation).where(
        SharePurchaseAllocation.employee_id == employee_id, SharePurchaseAllocation.state == "ALLOCATED")).all()
    purchase_cost = sum((Decimal(row.cost_jpy) for row in allocations), Decimal("0"))
    expected_cash = Decimal(member.opening_cash_jpy) + Decimal(posted_cash or 0) + Decimal(incentives or 0) - purchase_cost
    expected_units = Decimal(member.opening_units) + sum((Decimal(row.units) for row in allocations), Decimal("0"))
    transfers = db.scalars(select(ShareTransferRequest).where(
        ShareTransferRequest.tenant_id == tenant_id, ShareTransferRequest.employee_id == employee_id)).all()
    expected_units -= sum((Decimal(row.units) for row in transfers if row.state == "COMPLETED"), Decimal("0"))
    if cash != expected_cash or shares != expected_units:
        raise ApiError(409, "RECONCILIATION_FAILED", "Shareholding cash or units do not reconcile.")
    pending = sum((Decimal(row.units) for row in transfers if row.state not in {"COMPLETED", "REJECTED", "CANCELLED"}), Decimal("0"))
    whole_available = max(shares - pending, Decimal("0")).to_integral_value(rounding=ROUND_DOWN)
    return {"tenant_id": tenant_id, "employee_id": employee_id, "as_of": SNAPSHOT.date(), "currency": "JPY",
            "ownership_basis": "SHAREHOLDING_ASSOCIATION_BENEFICIAL_INTEREST",
            "snapshot_age_days": max((date.today() - SNAPSHOT.date()).days, 0),
            "plan": {"id": plan.id, "name": plan.name, "issuer": plan.issuer,
                                            "rule_source_reference": rule.source_reference,
                                            "rule_effective_on": rule.effective_on,
                                            "fractional_beneficial_units": rule.fractional_beneficial_units,
                                            "next_purchase_date": plan.next_purchase_date, "status": plan.status,
                                            "incentive_percent": str(plan.incentive_percent),
                                            "minimum_monthly_jpy": money(plan.minimum_monthly_jpy),
                                            "maximum_monthly_jpy": money(plan.maximum_monthly_jpy)},
            "membership": {"id": member.id, "status": member.status, "joined_on": member.joined_on},
            "shares_held": units(shares), "uninvested_cash_jpy": money(cash),
            "available_transfer_units": units(whole_available),
            "posted_employee_cash_jpy": money(posted_cash or 0), "posted_incentive_cash_jpy": money(incentives or 0),
            "settled_purchase_cost_jpy": money(purchase_cost),
            "reconciled": True, "source_reference": member.id}


def record_access(db: Session, request: Request, claims: dict, outcome: str = "permitted", reason: str = "OK"):
    audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"],
          employee_id=claims["employee_id"], service="stock", outcome=outcome, reason=reason)


def bounded_dates(start: date | None, end: date | None):
    if start and end and start > end:
        raise ApiError(422, "INVALID_DATE_RANGE", "The start date must not be after the end date.")


@router.get("/client/me/shareholding/summary")
def client_summary(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("stock"))):
    result = stock_summary(db, claims["tenant_id"], claims["employee_id"])
    record_access(db, request, claims)
    return result


@router.get("/client/me/shareholding/contributions")
def client_contributions(request: Request, start: date | None = Query(None, alias="from"),
                         end: date | None = Query(None, alias="to"),
                         db: Session = Depends(get_db), claims: dict = Depends(require_client("stock"))):
    bounded_dates(start, end)
    plan, _ = membership(db, claims["tenant_id"], claims["employee_id"])
    query = (select(SharePayrollLine, SharePayrollBatch).join(SharePayrollBatch)
             .where(SharePayrollLine.employee_id == claims["employee_id"],
                    SharePayrollBatch.plan_id == plan.id))
    if start:
        query = query.where(SharePayrollBatch.period >= start)
    if end:
        query = query.where(SharePayrollBatch.period <= end)
    rows = db.execute(query.order_by(SharePayrollBatch.period.desc())).all()
    result = {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"],
              "as_of": SNAPSHOT.date(), "currency": "JPY",
              "contributions": [{"period": batch.period, "source_reference": batch.source_reference,
                                 "rule_source_reference": (
                                     db.get(ShareholdingRuleVersion, db.get(SharePayrollRuleLink, batch.id).rule_id).source_reference
                                     if db.get(SharePayrollRuleLink, batch.id) else None),
                                 "amount_jpy": money(line.amount_jpy), "incentive_jpy": money(line.incentive_jpy),
                                 "state": line.state, "rejection_reason": line.rejection_reason}
                                for line, batch in rows]}
    record_access(db, request, claims)
    return result


@router.get("/client/me/shareholding/purchases")
def client_purchases(request: Request, start: date | None = Query(None, alias="from"),
                     end: date | None = Query(None, alias="to"),
                     db: Session = Depends(get_db), claims: dict = Depends(require_client("stock"))):
    bounded_dates(start, end)
    membership(db, claims["tenant_id"], claims["employee_id"])
    query = (select(SharePurchaseAllocation, SharePurchaseCycle).join(SharePurchaseCycle)
             .where(SharePurchaseAllocation.employee_id == claims["employee_id"]))
    if start:
        query = query.where(SharePurchaseCycle.trade_date >= start)
    if end:
        query = query.where(SharePurchaseCycle.trade_date <= end)
    rows = db.execute(query.order_by(SharePurchaseCycle.trade_date.desc())).all()
    result = {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"],
              "as_of": SNAPSHOT.date(), "currency": "JPY",
              "purchases": [{"source_reference": cycle.source_reference, "trade_date": cycle.trade_date,
                             "settlement_date": cycle.settlement_date, "state": cycle.state,
                             "unit_price_jpy": money(cycle.unit_price_jpy), "units": units(allocation.units),
                             "cost_jpy": money(allocation.cost_jpy), "allocation_state": allocation.state}
                            for allocation, cycle in rows]}
    record_access(db, request, claims)
    return result


@router.get("/client/me/shareholding/dividends")
def client_dividends(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("stock"))):
    membership(db, claims["tenant_id"], claims["employee_id"])
    rows = [row for row in journal(db, claims["tenant_id"], claims["employee_id"])
            if row.event_type == "ASSOCIATION_DIVIDEND_POSTED"]
    result = {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"],
              "as_of": SNAPSHOT.date(), "currency": "JPY",
              "dividends": [{"id": row.id, "source_reference": row.source_reference,
                             "payment_date": row.effective_at.date(), "amount_jpy": money(row.amount_jpy),
                             "state": "POSTED"} for row in rows]}
    record_access(db, request, claims)
    return result


@router.get("/client/me/shareholding/ledger")
def client_ledger(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("stock"))):
    membership(db, claims["tenant_id"], claims["employee_id"])
    result = {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"],
              "as_of": SNAPSHOT.date(), "currency": "JPY",
              "events": [ledger_row(row) for row in journal(db, claims["tenant_id"], claims["employee_id"])]}
    record_access(db, request, claims)
    return result


@router.get("/client/me/shareholding/transfers/{request_id}")
def client_transfer(request_id: str, request: Request, db: Session = Depends(get_db),
                    claims: dict = Depends(require_client("stock"))):
    row = db.get(ShareTransferRequest, request_id)
    if not row or row.tenant_id != claims["tenant_id"] or row.employee_id != claims["employee_id"]:
        record_access(db, request, claims, "denied", "RESOURCE_NOT_ACCESSIBLE")
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Transfer request is not available.")
    record_access(db, request, claims)
    return {"as_of": SNAPSHOT.date(), **transfer_row(row)}


class TransferDraft(BaseModel):
    units: Decimal
    recipient_account_reference: str = Field(min_length=5, max_length=60)


@router.post("/client/me/shareholding/transfer-drafts", status_code=201)
def client_transfer_draft(body: TransferDraft, request: Request,
                          idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=80),
                          db: Session = Depends(get_db), claims: dict = Depends(require_client("stock", "draft"))):
    tenant_id, employee_id = claims["tenant_id"], claims["employee_id"]
    plan, member = membership(db, tenant_id, employee_id)
    existing = db.scalar(select(ShareTransferRequest).where(
        ShareTransferRequest.tenant_id == tenant_id, ShareTransferRequest.employee_id == employee_id,
        ShareTransferRequest.idempotency_key == idempotency_key))
    if existing:
        if existing.units != body.units or existing.recipient_account_reference != body.recipient_account_reference:
            record_access(db, request, claims, "denied", "DUPLICATE_REQUEST")
            raise ApiError(409, "DUPLICATE_REQUEST", "The request key was already used for different details.")
        record_access(db, request, claims)
        return transfer_row(existing)
    if body.units <= 0 or body.units != body.units.to_integral_value() or body.units < plan.minimum_transfer_units:
        record_access(db, request, claims, "denied", "INVALID_AMOUNT")
        raise ApiError(422, "INVALID_AMOUNT", "Enter a whole-share quantity allowed by the plan.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{4,59}", body.recipient_account_reference):
        record_access(db, request, claims, "denied", "INVALID_PLAN_RULE")
        raise ApiError(422, "INVALID_PLAN_RULE", "The recipient account reference is invalid.")
    try:
        eligible_recipient(db, tenant_id, employee_id, body.recipient_account_reference, plan)
    except ApiError:
        record_access(db, request, claims, "denied", "RECIPIENT_ACCOUNT_NOT_ELIGIBLE")
        raise
    if member.status != "ACTIVE":
        record_access(db, request, claims, "denied", "STATE_CONFLICT")
        raise ApiError(409, "STATE_CONFLICT", "The membership is not active.")
    available = Decimal(stock_summary(db, tenant_id, employee_id)["available_transfer_units"])
    if body.units > available:
        record_access(db, request, claims, "denied", "INVALID_AMOUNT")
        raise ApiError(422, "INVALID_AMOUNT", "The requested quantity exceeds available whole shares.")
    request_id = "TR-" + uuid.uuid5(uuid.NAMESPACE_URL, f"{tenant_id}:{employee_id}:{idempotency_key}").hex[:12].upper()
    row = ShareTransferRequest(id=request_id, tenant_id=tenant_id, employee_id=employee_id,
                               plan_id=plan.id, units=body.units,
                               recipient_account_reference=body.recipient_account_reference,
                               state="REQUESTED", idempotency_key=idempotency_key, correlation_id=request_id)
    db.add(row)
    db.add(WorkflowTask(id=f"TASK-{request_id}", tenant_id=tenant_id, service="stock",
                        employee_id=employee_id, operation_key="share_transfer",
                        resource_id=request_id, state="REQUESTED", reviewer_role="plan_operator",
                        evidence_reference=body.recipient_account_reference))
    db.add(WorkflowTransition(task_id=f"TASK-{request_id}", from_state=None,
                              to_state="REQUESTED", actor=claims["sub"],
                              reason="Transfer request submitted"))
    record_access(db, request, claims, "changed", "TRANSFER_DRAFT_CREATED")
    return transfer_row(row)


TRANSFER_STATES = {
    "REQUESTED": {"ELIGIBILITY_CHECKED", "REJECTED", "CANCELLED"},
    "ELIGIBILITY_CHECKED": {"CORPORATE_APPROVED", "REJECTED", "CANCELLED"},
    "CORPORATE_APPROVED": {"PROVIDER_FORWARDED", "REJECTED", "CANCELLED"},
    "PROVIDER_FORWARDED": {"COMPLETED", "REJECTED"},
}


class TransferReview(BaseModel):
    state: str
    reason: str = Field(min_length=3, max_length=200)
    confirmation_reference: str | None = None


class PayrollLineInput(BaseModel):
    employee_id: str
    amount_jpy: Decimal
    incentive_jpy: Decimal | None = None


class PayrollBatchInput(BaseModel):
    period: date
    source_reference: str = Field(min_length=5, max_length=80)
    expected_jpy: Decimal
    lines: list[PayrollLineInput] = Field(min_length=1)


class StateInput(BaseModel):
    state: str
    reason: str = Field(min_length=3, max_length=200)


def admin_context(request: Request, claims: dict, operation: str):
    request.state.operation = operation
    request.state.principal_scopes = ",".join(claims.get("scopes") or [])


@router.post("/admin/tenants/{tenant_id}/shareholding/payroll-batches", status_code=201)
def admin_receive_payroll(tenant_id: str, body: PayrollBatchInput, request: Request,
                          db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    admin_context(request, claims, "receive_payroll")
    plan = tenant_plan(db, tenant_id)
    rule = rule_for_period(db, plan.id, body.period)
    if body.period.day != 1 or body.period > SNAPSHOT.date():
        raise ApiError(422, "INVALID_DATE_RANGE", "Payroll period must be a completed month.")
    if body.expected_jpy < 0 or any(line.amount_jpy <= 0 or
                                    (line.incentive_jpy is not None and line.incentive_jpy < 0)
                                    for line in body.lines):
        raise ApiError(422, "INVALID_AMOUNT", "Payroll amounts must be positive.")
    for line in body.lines:
        expected_incentive = (line.amount_jpy * Decimal(rule.incentive_percent) / 100).quantize(Decimal("0.01"))
        if line.incentive_jpy is not None and line.incentive_jpy != expected_incentive:
            raise ApiError(422, "INVALID_PLAN_RULE", "Employer incentive does not match the effective plan rule.")
    if len({line.employee_id for line in body.lines}) != len(body.lines):
        raise ApiError(409, "DUPLICATE_REQUEST", "An employee appears more than once in the batch.")
    existing = db.scalar(select(SharePayrollBatch).where(
        SharePayrollBatch.plan_id == plan.id, SharePayrollBatch.period == body.period,
        SharePayrollBatch.source_reference == body.source_reference))
    if existing:
        raise ApiError(409, "DUPLICATE_REQUEST", "This payroll source has already been received.")
    for line in body.lines:
        membership(db, tenant_id, line.employee_id)
        posted = db.scalar(select(SharePayrollLine.id).join(SharePayrollBatch).where(
            SharePayrollLine.employee_id == line.employee_id,
            SharePayrollLine.state == "POSTED", SharePayrollBatch.period == body.period))
        if posted:
            raise ApiError(409, "DUPLICATE_REQUEST", "A payroll contribution is already posted for this employee and period.")
    batch_id = "PAY-" + uuid.uuid5(uuid.NAMESPACE_URL, f"{plan.id}:{body.period}:{body.source_reference}").hex[:12].upper()
    received = sum((line.amount_jpy for line in body.lines), Decimal("0"))
    db.add(SharePayrollBatch(id=batch_id, plan_id=plan.id, period=body.period,
                             source_reference=body.source_reference, expected_jpy=body.expected_jpy,
                             received_jpy=received, state="RECEIVED"))
    db.add(SharePayrollRuleLink(batch_id=batch_id, rule_id=rule.id))
    for line in body.lines:
        expected_incentive = (line.amount_jpy * Decimal(rule.incentive_percent) / 100).quantize(Decimal("0.01"))
        db.add(SharePayrollLine(id=f"{batch_id}-{line.employee_id}", batch_id=batch_id,
                                employee_id=line.employee_id, amount_jpy=line.amount_jpy,
                                incentive_jpy=expected_incentive, state="RECEIVED"))
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service="stock", outcome="changed", reason="PAYROLL_RECEIVED")
    return {"batch_id": batch_id, "state": "RECEIVED", "received_jpy": money(received)}


@router.patch("/admin/tenants/{tenant_id}/shareholding/payroll-batches/{batch_id}")
def admin_review_payroll(tenant_id: str, batch_id: str, body: StateInput, request: Request,
                         db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    admin_context(request, claims, "review_payroll")
    plan = tenant_plan(db, tenant_id)
    batch = db.get(SharePayrollBatch, batch_id)
    if not batch or batch.plan_id != plan.id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Payroll batch is not available.")
    if body.state == batch.state:
        return {"batch_id": batch.id, "state": batch.state}
    if (batch.state, body.state) not in {("RECEIVED", "VALIDATED"), ("VALIDATED", "POSTED"),
                                         ("RECEIVED", "REJECTED"), ("VALIDATED", "REJECTED")}:
        raise ApiError(409, "STATE_CONFLICT", "This payroll state change is not allowed.")
    lines = db.scalars(select(SharePayrollLine).where(SharePayrollLine.batch_id == batch_id)).all()
    if body.state == "VALIDATED":
        if Decimal(batch.received_jpy) != Decimal(batch.expected_jpy):
            raise ApiError(409, "RECONCILIATION_FAILED", "Received payroll does not match the expected amount.")
        for line in lines:
            plan_membership = membership(db, tenant_id, line.employee_id)[1]
            election = db.scalar(select(ContributionElection).where(
                ContributionElection.membership_id == plan_membership.id,
                ContributionElection.effective_period <= batch.period,
                ContributionElection.state == "EFFECTIVE").order_by(ContributionElection.effective_period.desc()))
            if plan_membership.status != "ACTIVE" or not plan.minimum_monthly_jpy <= line.amount_jpy <= plan.maximum_monthly_jpy:
                raise ApiError(422, "INVALID_PLAN_RULE", "A payroll line is outside membership or plan rules.")
            if not election or line.amount_jpy != election.monthly_jpy:
                raise ApiError(409, "RECONCILIATION_FAILED", "Payroll amount does not match the effective election.")
            line.state = "VALIDATED"
    elif body.state == "POSTED":
        for line in lines:
            if line.state != "VALIDATED":
                raise ApiError(409, "STATE_CONFLICT", "Every line must be validated before posting.")
            line.state = "POSTED"
            employee = db.get(Employee, line.employee_id)
            for kind, amount in [("PAYROLL_POSTED", Decimal(line.amount_jpy)),
                                 ("INCENTIVE_POSTED", Decimal(line.incentive_jpy))]:
                if amount:
                    event_id = f"EV-{kind}-{batch.id}-{line.employee_id}"
                    if not db.get(FinancialEvent, event_id):
                        db.add(FinancialEvent(id=event_id, tenant_id=employee.tenant_id,
                                              employee_id=line.employee_id, service="stock",
                                              event_type=kind, source_reference=batch.source_reference,
                                              idempotency_key=event_id, correlation_id=batch.id,
                                              occurred_at=at_day(batch.period), effective_at=at_day(batch.period),
                                              recorded_at=SNAPSHOT, amount_jpy=amount, quantity=Decimal("0"),
                                              actor=claims["sub"]))
    else:
        for line in lines:
            line.state = "REJECTED"
            line.rejection_reason = body.reason
    batch.state = body.state
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service="stock", outcome="changed", reason=f"PAYROLL_{body.state}")
    return {"batch_id": batch.id, "state": batch.state}


class PurchaseAllocationInput(BaseModel):
    employee_id: str
    units: Decimal


class PurchaseCycleInput(BaseModel):
    source_reference: str = Field(min_length=5, max_length=80)
    trade_date: date
    unit_price_jpy: Decimal
    acquired_units: Decimal
    allocations: list[PurchaseAllocationInput] = Field(min_length=1)


@router.post("/admin/tenants/{tenant_id}/shareholding/purchase-cycles", status_code=201)
def admin_create_purchase(tenant_id: str, body: PurchaseCycleInput, request: Request,
                          db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    admin_context(request, claims, "create_purchase")
    plan = tenant_plan(db, tenant_id)
    if body.trade_date > SNAPSHOT.date():
        raise ApiError(422, "INVALID_DATE_RANGE", "Trade date is after the available snapshot.")
    if body.unit_price_jpy <= 0 or body.acquired_units <= 0 or any(row.units <= 0 for row in body.allocations):
        raise ApiError(422, "INVALID_AMOUNT", "Price and units must be positive.")
    if not plan.fractional_units_allowed and (
        body.acquired_units != body.acquired_units.to_integral_value() or
        any(row.units != row.units.to_integral_value() for row in body.allocations)):
        raise ApiError(422, "INVALID_PLAN_RULE", "This plan requires whole share allocations.")
    if any((row.units * body.unit_price_jpy) != (row.units * body.unit_price_jpy).quantize(Decimal("0.01"))
           for row in body.allocations):
        raise ApiError(422, "INVALID_AMOUNT", "Allocation cost must be expressible in yen and sen.")
    if len({row.employee_id for row in body.allocations}) != len(body.allocations):
        raise ApiError(409, "DUPLICATE_REQUEST", "An employee appears more than once in the allocation.")
    if sum((row.units for row in body.allocations), Decimal("0")) > body.acquired_units:
        raise ApiError(409, "RECONCILIATION_FAILED", "Allocated units exceed acquired units.")
    if db.scalar(select(SharePurchaseCycle.id).where(SharePurchaseCycle.plan_id == plan.id,
                                                      SharePurchaseCycle.source_reference == body.source_reference)):
        raise ApiError(409, "DUPLICATE_REQUEST", "This purchase source already exists.")
    for row in body.allocations:
        membership(db, tenant_id, row.employee_id)
    cycle_id = "BUY-" + uuid.uuid5(uuid.NAMESPACE_URL, f"{plan.id}:{body.source_reference}").hex[:12].upper()
    db.add(SharePurchaseCycle(id=cycle_id, plan_id=plan.id, source_reference=body.source_reference,
                              trade_date=body.trade_date, settlement_date=None,
                              unit_price_jpy=body.unit_price_jpy, acquired_units=body.acquired_units,
                              state="CREATED"))
    for row in body.allocations:
        db.add(SharePurchaseAllocation(id=f"ALLOC-{cycle_id}-{row.employee_id}", cycle_id=cycle_id,
                                       employee_id=row.employee_id, units=row.units,
                                       cost_jpy=row.units * body.unit_price_jpy, state="PENDING"))
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service="stock", outcome="changed", reason="PURCHASE_CREATED")
    return {"cycle_id": cycle_id, "state": "CREATED"}


@router.patch("/admin/tenants/{tenant_id}/shareholding/purchase-cycles/{cycle_id}")
def admin_review_purchase(tenant_id: str, cycle_id: str, body: StateInput, request: Request,
                          db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    admin_context(request, claims, "review_purchase")
    plan = tenant_plan(db, tenant_id)
    cycle = db.get(SharePurchaseCycle, cycle_id)
    if not cycle or cycle.plan_id != plan.id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Purchase cycle is not available.")
    if body.state == cycle.state:
        return {"cycle_id": cycle.id, "state": cycle.state}
    if (cycle.state, body.state) not in {("CREATED", "PRICED"), ("PRICED", "SETTLED"),
                                         ("SETTLED", "ALLOCATED"), ("CREATED", "FAILED"),
                                         ("PRICED", "FAILED")}:
        raise ApiError(409, "STATE_CONFLICT", "This purchase state change is not allowed.")
    allocations = db.scalars(select(SharePurchaseAllocation).where(SharePurchaseAllocation.cycle_id == cycle_id)).all()
    if body.state == "ALLOCATED":
        allocated = sum((Decimal(row.units) for row in allocations), Decimal("0"))
        if allocated != Decimal(cycle.acquired_units):
            raise ApiError(409, "RECONCILIATION_FAILED", "Allocated units must equal acquired units.")
        for row in allocations:
            cost = Decimal(row.cost_jpy)
            _, available_cash = balances(db, tenant_id, row.employee_id)
            if cost > available_cash:
                raise ApiError(409, "RECONCILIATION_FAILED", "Participant cash is insufficient for allocation.")
        for row in allocations:
            row.state = "ALLOCATED"
            event_id = f"EV-ALLOC-{cycle.id}-{row.employee_id}"
            if not db.get(FinancialEvent, event_id):
                db.add(FinancialEvent(id=event_id, tenant_id=tenant_id,
                                      employee_id=row.employee_id, service="stock",
                                      event_type="PURCHASE_ALLOCATED", source_reference=cycle.source_reference,
                                      idempotency_key=event_id, correlation_id=cycle.id,
                                      occurred_at=at_day(cycle.trade_date), effective_at=at_day(cycle.trade_date),
                                      recorded_at=SNAPSHOT, amount_jpy=-Decimal(row.cost_jpy),
                                      quantity=Decimal(row.units), actor=claims["sub"]))
    if body.state == "SETTLED":
        cycle.settlement_date = cycle.trade_date
    cycle.state = body.state
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service="stock", outcome="changed", reason=f"PURCHASE_{body.state}")
    return {"cycle_id": cycle.id, "state": cycle.state}


@router.patch("/admin/tenants/{tenant_id}/shareholding/transfers/{request_id}")
def admin_review_transfer(tenant_id: str, request_id: str, body: TransferReview, request: Request,
                          db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    admin_context(request, claims, "review_transfer")
    row = db.get(ShareTransferRequest, request_id)
    if not row or row.tenant_id != tenant_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Transfer request is not available.")
    if body.state == row.state:
        return transfer_row(row)
    if body.state not in TRANSFER_STATES.get(row.state, set()):
        raise ApiError(409, "STATE_CONFLICT", "This transfer state change is not allowed.")
    previous = row.state
    if body.state == "COMPLETED":
        account = eligible_recipient(db, tenant_id, row.employee_id, row.recipient_account_reference,
                                     tenant_plan(db, tenant_id))
        if not body.confirmation_reference or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{7,79}", body.confirmation_reference):
            raise ApiError(422, "CONFIRMATION_REQUIRED", "A valid settlement confirmation reference is required.")
        if db.scalar(select(CustodySettlementConfirmation).where(
            CustodySettlementConfirmation.confirmation_reference == body.confirmation_reference)):
            raise ApiError(409, "DUPLICATE_REQUEST", "This settlement confirmation has already been recorded.")
        shares, _ = balances(db, tenant_id, row.employee_id)
        if Decimal(row.units) > shares:
            raise ApiError(409, "RECONCILIATION_FAILED", "The transfer exceeds current shares.")
        when = SNAPSHOT

        db.add(CustodySettlementConfirmation(transfer_id=row.id, account_id=account.id,
                                             confirmation_reference=body.confirmation_reference,
                                             confirmed_at=when, state="SETTLED_CONFIRMED"))
        for service, event_type, quantity in [
            ("stock", "TRANSFER_OUT", -Decimal(row.units)),
            ("custody", "TRANSFER_IN", Decimal(row.units)),
        ]:
            event_id = f"EV-{service.upper()}-{row.id}"
            if not db.get(FinancialEvent, event_id):
                db.add(FinancialEvent(id=event_id, tenant_id=tenant_id, employee_id=row.employee_id,
                                      service=service, event_type=event_type, source_reference=row.id,
                                      idempotency_key=event_id, correlation_id=row.correlation_id,
                                      occurred_at=when, effective_at=when, recorded_at=when,
                                      amount_jpy=Decimal("0"), quantity=quantity, actor=claims["sub"]))
    row.state = body.state
    task = db.get(WorkflowTask, f"TASK-{row.id}")
    task.state = body.state
    task.updated_at = datetime.now(timezone.utc)
    db.add(WorkflowTransition(task_id=task.id, from_state=previous, to_state=body.state,
                              actor=claims["sub"], reason=body.reason))
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=row.employee_id,
          service="stock", outcome="changed", reason=f"TRANSFER_{body.state}")
    return transfer_row(row)


@router.get("/admin/tenants/{tenant_id}/shareholding/operations")
def admin_stock_operations(tenant_id: str, request: Request, db: Session = Depends(get_db),
                           claims: dict = Depends(require_admin())):
    admin_context(request, claims, "view_stock_operations")
    plan = tenant_plan(db, tenant_id)
    rule = rule_for_period(db, plan.id, SNAPSHOT.date())
    members = db.scalars(select(ShareMembership).where(ShareMembership.plan_id == plan.id).order_by(ShareMembership.employee_id)).all()
    batches = db.scalars(select(SharePayrollBatch).where(SharePayrollBatch.plan_id == plan.id).order_by(SharePayrollBatch.period.desc())).all()
    cycles = db.scalars(select(SharePurchaseCycle).where(SharePurchaseCycle.plan_id == plan.id).order_by(SharePurchaseCycle.trade_date.desc())).all()
    breaks = db.scalars(select(ReconciliationCase).where(ReconciliationCase.tenant_id == tenant_id,
                                                          ReconciliationCase.service == "stock")).all()
    transfers = db.scalars(select(ShareTransferRequest).where(ShareTransferRequest.tenant_id == tenant_id).order_by(ShareTransferRequest.submitted_at.desc())).all()
    statements = db.scalars(select(OperationalStatement).where(OperationalStatement.tenant_id == tenant_id,
                                                                OperationalStatement.service == "stock")).all()
    result = {"tenant_id": tenant_id, "as_of": SNAPSHOT.date(),
              "plan": {"id": plan.id, "name": plan.name, "issuer": plan.issuer,
                       "rule_source_reference": rule.source_reference,
                       "rule_effective_on": rule.effective_on,
                       "fractional_beneficial_units": rule.fractional_beneficial_units,
                       "minimum_monthly_jpy": money(plan.minimum_monthly_jpy),
                       "maximum_monthly_jpy": money(plan.maximum_monthly_jpy),
                       "incentive_percent": str(plan.incentive_percent),
                       "next_purchase_date": plan.next_purchase_date, "status": plan.status},
              "members": [{"employee_id": row.employee_id, "display_name": db.get(Employee, row.employee_id).display_name,
                           "status": row.status, "joined_on": row.joined_on,
                           "shares_held": stock_summary(db, tenant_id, row.employee_id)["shares_held"],
                           "cash_jpy": stock_summary(db, tenant_id, row.employee_id)["uninvested_cash_jpy"]}
                          for row in members],
              "payroll_batches": [{"id": row.id, "period": row.period, "source_reference": row.source_reference,
                                   "expected_jpy": money(row.expected_jpy), "received_jpy": money(row.received_jpy),
                                   "state": row.state,
                                   "failed_lines": db.scalar(select(func.count()).select_from(SharePayrollLine).where(
                                       SharePayrollLine.batch_id == row.id, SharePayrollLine.state == "REJECTED"))}
                                  for row in batches],
              "purchase_cycles": [{"id": row.id, "trade_date": row.trade_date,
                                   "settlement_date": row.settlement_date, "unit_price_jpy": money(row.unit_price_jpy),
                                   "acquired_units": units(row.acquired_units), "state": row.state}
                                  for row in cycles],
              "exceptions": [{"id": row.id, "employee_id": row.employee_id, "source_reference": row.source_reference,
                              "break_type": row.break_type, "expected_jpy": money(row.expected_jpy or 0),
                              "actual_jpy": money(row.actual_jpy or 0), "status": row.status,
                              "owner": row.owner, "resolution_note": row.resolution_note} for row in breaks],
              "transfers": [transfer_row(row) for row in transfers],
              "statements": [{"id": row.id, "employee_id": row.employee_id, "period": row.period,
                              "as_of": row.as_of, "version": row.version,
                              "source_reference": row.source_reference} for row in statements]}
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service="stock", outcome="permitted", reason="OK")
    return result

