"""Fund positions and future-contribution allocation instructions."""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .details import growth_projection
from .models import Employee, PensionAccount
from .security import ApiError, audit, require_admin, require_client
from .v2_models import (
    FinancialEvent, OperationalStatement, PensionAllocationInstruction,
    PensionContributionRecord, PensionFund, PensionFundPosition, PensionFutureAllocation,
    PensionInstructionLine, PensionNav, PensionPlanV2, PensionSwitchDraft, ReconciliationCase,
)
from .v2_seed import SNAPSHOT

router = APIRouter(prefix="/api/v2", tags=["Pension operations"])


def money(value):
    return f"{Decimal(value):.2f}"


def plan_for_tenant(db: Session, tenant_id: str):
    plan = db.scalar(select(PensionPlanV2).where(PensionPlanV2.tenant_id == tenant_id))
    if not plan:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Pension plan is not available.")
    return plan


def account_for_employee(db: Session, tenant_id: str, employee_id: str):
    plan = plan_for_tenant(db, tenant_id)
    employee = db.get(Employee, employee_id)
    if not employee or employee.tenant_id != tenant_id or not db.get(PensionAccount, employee_id):
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Pension account is not available.")
    return plan


def current_nav(db: Session, fund_id: str):
    row = db.scalar(select(PensionNav).where(PensionNav.fund_id == fund_id).order_by(PensionNav.valuation_date.desc()))
    if not row:
        raise ApiError(503, "DATA_SNAPSHOT_UNAVAILABLE", "A fund valuation is unavailable.")
    return row


def positions(db: Session, tenant_id: str, employee_id: str):
    plan = account_for_employee(db, tenant_id, employee_id)
    rows = []
    for position in db.scalars(select(PensionFundPosition).where(PensionFundPosition.employee_id == employee_id)):
        fund = db.get(PensionFund, position.fund_id)
        if fund.plan_id != plan.id:
            raise ApiError(409, "RECONCILIATION_FAILED", "A fund position is outside the employee plan.")
        nav = current_nav(db, fund.id)
        value = (Decimal(position.units) * Decimal(nav.nav_jpy)).quantize(Decimal("0.01"))
        rows.append({"fund_id": fund.id, "fund_name": fund.name, "category": fund.category,
                     "units": f"{Decimal(position.units):.6f}", "nav_jpy": money(nav.nav_jpy),
                     "nav_date": nav.valuation_date, "nav_age_days": (SNAPSHOT.date() - nav.valuation_date).days,
                     "value_jpy": money(value), "annual_fee_percent": str(fund.annual_fee_percent)})
    return rows


def pension_account(db: Session, tenant_id: str, employee_id: str):
    holdings = positions(db, tenant_id, employee_id)
    position_value = sum((Decimal(row["value_jpy"]) for row in holdings), Decimal("0"))
    events = db.scalars(select(FinancialEvent).where(
        FinancialEvent.tenant_id == tenant_id, FinancialEvent.employee_id == employee_id,
        FinancialEvent.service == "pension")).all()
    event_value = sum((Decimal(row.amount_jpy) for row in events), Decimal("0"))
    if position_value != event_value:
        raise ApiError(409, "RECONCILIATION_FAILED", "Pension fund value and activity do not reconcile.")
    return {"tenant_id": tenant_id, "employee_id": employee_id, "as_of": SNAPSHOT.date(),
            "currency": "JPY", "balance_jpy": money(position_value),
            "positions": holdings, "reconciled": True,
            "plan_id": plan_for_tenant(db, tenant_id).id}


def client_audit(db: Session, request: Request, claims: dict, outcome="permitted", reason="OK"):
    audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"],
          employee_id=claims["employee_id"], service="pension", outcome=outcome, reason=reason)


@router.get("/client/me/pension/account")
def client_account(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("pension"))):
    result = pension_account(db, claims["tenant_id"], claims["employee_id"])
    client_audit(db, request, claims)
    return result


@router.get("/client/me/pension/positions")
def client_positions(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("pension"))):
    result = {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"],
              "as_of": SNAPSHOT.date(), "currency": "JPY",
              "positions": positions(db, claims["tenant_id"], claims["employee_id"])}
    client_audit(db, request, claims)
    return result


@router.get("/client/me/pension/contributions")
def client_contributions(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("pension"))):
    account_for_employee(db, claims["tenant_id"], claims["employee_id"])
    rows = db.scalars(select(PensionContributionRecord).where(
        PensionContributionRecord.employee_id == claims["employee_id"]).order_by(PensionContributionRecord.period.desc())).all()
    result = {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"],
              "as_of": SNAPSHOT.date(), "currency": "JPY",
              "contributions": [{"source_reference": row.source_reference, "period": row.period,
                                 "employee_jpy": money(row.employee_jpy), "employer_jpy": money(row.employer_jpy),
                                 "state": row.state, "rejection_reason": row.rejection_reason} for row in rows]}
    client_audit(db, request, claims)
    return result


@router.get("/client/me/pension/funds")
def client_funds(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("pension"))):
    plan = account_for_employee(db, claims["tenant_id"], claims["employee_id"])
    rows = db.scalars(select(PensionFund).where(PensionFund.plan_id == plan.id)).all()
    result = {"tenant_id": claims["tenant_id"], "as_of": SNAPSHOT.date(),
              "funds": [{"id": row.id, "name": row.name, "category": row.category,
                         "annual_fee_percent": str(row.annual_fee_percent), "eligible": row.eligible,
                         "latest_nav_jpy": money(current_nav(db, row.id).nav_jpy),
                         "nav_date": current_nav(db, row.id).valuation_date} for row in rows]}
    client_audit(db, request, claims)
    return result


@router.get("/client/me/pension/allocation")
def client_allocation(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("pension"))):
    account_for_employee(db, claims["tenant_id"], claims["employee_id"])
    rows = db.scalars(select(PensionFutureAllocation).where(
        PensionFutureAllocation.employee_id == claims["employee_id"])).all()
    result = {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"],
              "as_of": SNAPSHOT.date(), "applies_to": "FUTURE_CONTRIBUTIONS_ONLY",
              "allocations": [{"fund_id": row.fund_id, "percentage": str(row.percentage),
                               "effective_period": row.effective_period} for row in rows]}
    client_audit(db, request, claims)
    return result


@router.get("/client/me/pension/projections")
def client_projections(request: Request, years: int = Query(20, ge=1, le=40),
                       monthly_jpy: int = Query(35000, ge=0, le=1_000_000),
                       annual_return_pct: Decimal = Query(Decimal("4"), ge=0, le=12),
                       db: Session = Depends(get_db), claims: dict = Depends(require_client("pension"))):
    account = pension_account(db, claims["tenant_id"], claims["employee_id"])
    result = {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"],
              "as_of": SNAPSHOT.date(), "currency": "JPY",
              "assumptions": {"monthly_jpy": monthly_jpy, "years": years,
                              "annual_return_pct": str(annual_return_pct),
                              "formula_id": "MONTH_END_COMPOUND_V1"},
              "projection": growth_projection(int(Decimal(account["balance_jpy"])), monthly_jpy,
                                               years, annual_return_pct)}
    client_audit(db, request, claims)
    return result


@router.get("/client/me/pension/instructions/{instruction_id}")
def client_instruction(instruction_id: str, request: Request, db: Session = Depends(get_db),
                       claims: dict = Depends(require_client("pension"))):
    row = db.get(PensionAllocationInstruction, instruction_id)
    if not row or row.tenant_id != claims["tenant_id"] or row.employee_id != claims["employee_id"]:
        client_audit(db, request, claims, "denied", "RESOURCE_NOT_ACCESSIBLE")
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Allocation instruction is not available.")
    result = instruction_json(db, row)
    client_audit(db, request, claims)
    return result


def instruction_json(db: Session, row: PensionAllocationInstruction):
    lines = db.scalars(select(PensionInstructionLine).where(PensionInstructionLine.instruction_id == row.id)).all()
    return {"instruction_id": row.id, "employee_id": row.employee_id, "state": row.state,
            "submitted_at": row.submitted_at, "applies_to": "FUTURE_CONTRIBUTIONS_ONLY",
            "allocations": [{"fund_id": line.fund_id, "percentage": str(line.percentage)} for line in lines]}


class AllocationLineInput(BaseModel):
    fund_id: str
    percentage: Decimal


class AllocationDraft(BaseModel):
    allocations: list[AllocationLineInput] = Field(min_length=1)


@router.post("/client/me/pension/allocation-drafts", status_code=201)
def client_allocation_draft(body: AllocationDraft, request: Request,
                            idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=80),
                            db: Session = Depends(get_db), claims: dict = Depends(require_client("pension", "draft"))):
    tenant_id, employee_id = claims["tenant_id"], claims["employee_id"]
    plan = account_for_employee(db, tenant_id, employee_id)
    existing = db.scalar(select(PensionAllocationInstruction).where(
        PensionAllocationInstruction.tenant_id == tenant_id,
        PensionAllocationInstruction.employee_id == employee_id,
        PensionAllocationInstruction.idempotency_key == idempotency_key))
    if existing:
        previous = {line["fund_id"]: Decimal(line["percentage"]) for line in instruction_json(db, existing)["allocations"]}
        requested = {line.fund_id: line.percentage for line in body.allocations}
        if previous != requested:
            client_audit(db, request, claims, "denied", "DUPLICATE_REQUEST")
            raise ApiError(409, "DUPLICATE_REQUEST", "The request key was already used for different allocations.")
        client_audit(db, request, claims)
        return instruction_json(db, existing)
    fund_ids = [line.fund_id for line in body.allocations]
    if len(set(fund_ids)) != len(fund_ids) or any(line.percentage < 0 for line in body.allocations) or sum(
        (line.percentage for line in body.allocations), Decimal("0")) != Decimal("100"):
        client_audit(db, request, claims, "denied", "INVALID_ALLOCATION")
        raise ApiError(422, "INVALID_ALLOCATION", "Future contribution allocations must total 100%.")
    for fund_id in fund_ids:
        fund = db.get(PensionFund, fund_id)
        if not fund or fund.plan_id != plan.id or not fund.eligible:
            client_audit(db, request, claims, "denied", "INVALID_ALLOCATION")
            raise ApiError(422, "INVALID_ALLOCATION", "A selected fund is not available in this plan.")
    instruction_id = "ALLOC-" + uuid.uuid5(uuid.NAMESPACE_URL, f"{tenant_id}:{employee_id}:{idempotency_key}").hex[:12].upper()
    row = PensionAllocationInstruction(id=instruction_id, tenant_id=tenant_id, employee_id=employee_id,
                                       state="DRAFT", idempotency_key=idempotency_key)
    db.add(row)
    for line in body.allocations:
        db.add(PensionInstructionLine(id=f"{instruction_id}-{line.fund_id}", instruction_id=instruction_id,
                                      fund_id=line.fund_id, percentage=line.percentage))
    client_audit(db, request, claims, "changed", "ALLOCATION_DRAFT_CREATED")
    return instruction_json(db, row)


class SwitchDraftInput(BaseModel):
    from_fund_id: str
    to_fund_id: str
    units: Decimal = Field(gt=0)


def switch_json(row: PensionSwitchDraft):
    return {"id": row.id, "employee_id": row.employee_id,
            "from_fund_id": row.from_fund_id, "to_fund_id": row.to_fund_id,
            "units": str(row.units), "state": row.state, "effect": "DRAFT_ONLY"}


@router.post("/client/me/pension/switch-drafts", status_code=201)
def client_switch_draft(body: SwitchDraftInput, request: Request,
                        idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=80),
                        db: Session = Depends(get_db),
                        claims: dict = Depends(require_client("pension", "draft"))):
    tenant_id, employee_id = claims["tenant_id"], claims["employee_id"]
    plan = account_for_employee(db, tenant_id, employee_id)
    existing = db.scalar(select(PensionSwitchDraft).where(
        PensionSwitchDraft.tenant_id == tenant_id, PensionSwitchDraft.employee_id == employee_id,
        PensionSwitchDraft.idempotency_key == idempotency_key))
    if existing:
        if (existing.from_fund_id, existing.to_fund_id, existing.units) != (
            body.from_fund_id, body.to_fund_id, body.units):
            client_audit(db, request, claims, "denied", "DUPLICATE_REQUEST")
            raise ApiError(409, "DUPLICATE_REQUEST", "Request key was already used for a different switch draft.")
        client_audit(db, request, claims)
        return switch_json(existing)
    source = db.get(PensionFund, body.from_fund_id)
    destination = db.get(PensionFund, body.to_fund_id)
    position = db.scalar(select(PensionFundPosition).where(
        PensionFundPosition.employee_id == employee_id,
        PensionFundPosition.fund_id == body.from_fund_id))
    if (not source or not destination or source.plan_id != plan.id or destination.plan_id != plan.id
            or not destination.eligible or source.id == destination.id or not position
            or body.units > position.units):
        client_audit(db, request, claims, "denied", "SWITCH_NOT_ELIGIBLE")
        raise ApiError(422, "SWITCH_NOT_ELIGIBLE", "The requested switch is outside current holdings or plan rules.")
    row = PensionSwitchDraft(id="SWD-" + uuid.uuid4().hex[:12].upper(), tenant_id=tenant_id,
                             employee_id=employee_id, from_fund_id=source.id,
                             to_fund_id=destination.id, units=body.units,
                             idempotency_key=idempotency_key, state="DRAFT")
    db.add(row)
    client_audit(db, request, claims, "changed", "SWITCH_DRAFT_CREATED")
    return switch_json(row)


@router.get("/client/me/pension/switch-drafts/{draft_id}")
def client_switch_detail(draft_id: str, request: Request, db: Session = Depends(get_db),
                         claims: dict = Depends(require_client("pension"))):
    row = db.get(PensionSwitchDraft, draft_id)
    if not row or row.tenant_id != claims["tenant_id"] or row.employee_id != claims["employee_id"]:
        client_audit(db, request, claims, "denied", "RESOURCE_NOT_ACCESSIBLE")
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Switch draft is not available.")
    client_audit(db, request, claims)
    return switch_json(row)


class InstructionReview(BaseModel):
    state: str
    reason: str = Field(min_length=3, max_length=200)


@router.patch("/admin/tenants/{tenant_id}/pension/instructions/{instruction_id}")
def admin_review_instruction(tenant_id: str, instruction_id: str, body: InstructionReview, request: Request,
                             db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    request.state.operation = "review_pension_instruction"
    request.state.principal_scopes = ",".join(claims.get("scopes") or [])
    row = db.get(PensionAllocationInstruction, instruction_id)
    if not row or row.tenant_id != tenant_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Allocation instruction is not available.")
    if body.state == row.state:
        return instruction_json(db, row)
    if (row.state, body.state) not in {("DRAFT", "VALIDATED"), ("VALIDATED", "ACCEPTED"),
                                       ("ACCEPTED", "EFFECTIVE_NEXT_CONTRIBUTION")}:
        raise ApiError(409, "STATE_CONFLICT", "This instruction state change is not allowed.")
    if body.state == "EFFECTIVE_NEXT_CONTRIBUTION":
        requested = {line.fund_id: line.percentage for line in db.scalars(select(PensionInstructionLine).where(
            PensionInstructionLine.instruction_id == row.id))}
        for current in db.scalars(select(PensionFutureAllocation).where(
            PensionFutureAllocation.employee_id == row.employee_id)):
            current.percentage = requested.pop(current.fund_id, Decimal("0"))
            current.effective_period = date(2026, 12, 1)
        for fund_id, percentage in requested.items():
            db.add(PensionFutureAllocation(id=f"FUT-{row.employee_id}-{fund_id}",
                                           employee_id=row.employee_id, fund_id=fund_id,
                                           percentage=percentage, effective_period=date(2026, 12, 1)))
    row.state = body.state
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=row.employee_id,
          service="pension", outcome="changed", reason=f"ALLOCATION_{body.state}")
    return instruction_json(db, row)


@router.get("/admin/tenants/{tenant_id}/pension/operations")
def admin_pension_operations(tenant_id: str, request: Request, db: Session = Depends(get_db),
                             claims: dict = Depends(require_admin())):
    request.state.operation = "view_pension_operations"
    request.state.principal_scopes = ",".join(claims.get("scopes") or [])
    plan = plan_for_tenant(db, tenant_id)
    accounts = db.scalars(select(PensionAccount).join(Employee, Employee.id == PensionAccount.employee_id)
                          .where(Employee.tenant_id == tenant_id)).all()
    funds = db.scalars(select(PensionFund).where(PensionFund.plan_id == plan.id)).all()
    cases = db.scalars(select(ReconciliationCase).where(ReconciliationCase.tenant_id == tenant_id,
                                                        ReconciliationCase.service == "pension")).all()
    instructions = db.scalars(select(PensionAllocationInstruction).where(
        PensionAllocationInstruction.tenant_id == tenant_id)).all()
    switch_drafts = db.scalars(select(PensionSwitchDraft).where(
        PensionSwitchDraft.tenant_id == tenant_id)).all()
    statements = db.scalars(select(OperationalStatement).where(
        OperationalStatement.tenant_id == tenant_id, OperationalStatement.service == "pension")).all()
    result = {"tenant_id": tenant_id, "as_of": SNAPSHOT.date(),
              "plan": {"id": plan.id, "name": plan.name, "status": plan.status, "effective_on": plan.effective_on},
              "accounts": [{"employee_id": row.employee_id,
                            "balance_jpy": pension_account(db, tenant_id, row.employee_id)["balance_jpy"],
                            "positions": pension_account(db, tenant_id, row.employee_id)["positions"]}
                           for row in accounts],
              "funds": [{"id": row.id, "name": row.name, "category": row.category,
                         "annual_fee_percent": str(row.annual_fee_percent),
                         "latest_nav_jpy": money(current_nav(db, row.id).nav_jpy)} for row in funds],
              "exceptions": [{"id": row.id, "employee_id": row.employee_id, "break_type": row.break_type,
                              "source_reference": row.source_reference, "status": row.status} for row in cases],
              "instructions": [instruction_json(db, row) for row in instructions],
              "switch_drafts": [switch_json(row) for row in switch_drafts],
              "statements": [{"id": row.id, "employee_id": row.employee_id,
                              "period": row.period, "as_of": row.as_of} for row in statements]}
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service="pension", outcome="permitted", reason="OK")
    return result

