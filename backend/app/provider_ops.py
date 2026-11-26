"""Provider work queue and source-derived operational reporting."""
from datetime import date, datetime, time, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalog import SERVICES
from .db import get_db
from .models import Employee, Tenant
from .security import ApiError, audit, require_admin
from .v2_models import (CaseResolution, EquityAward, EquityPlanV2,
                        FinancialEvent, OperationalStatement, ReconciliationCase,
                        WellnessContentV2, WorkflowTask, WorkflowTransition)
from .v2_seed import SNAPSHOT

router = APIRouter(prefix="/api/v2/admin/tenants/{tenant_id}", tags=["Provider operations"])


def scoped_tenant(db: Session, tenant_id: str):
    if not db.get(Tenant, tenant_id):
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Corporate client is not available.")


def case_json(db: Session, row: ReconciliationCase):
    resolution = db.get(CaseResolution, row.id)
    task = db.scalar(select(WorkflowTask).where(WorkflowTask.tenant_id == row.tenant_id,
                                                 WorkflowTask.resource_id == row.id))
    history = db.scalars(select(WorkflowTransition).where(
        WorkflowTransition.task_id == task.id).order_by(WorkflowTransition.id)).all() if task else []
    return {"id": row.id, "service": row.service, "employee_id": row.employee_id,
            "source_reference": row.source_reference, "break_type": row.break_type,
            "expected_jpy": str(row.expected_jpy) if row.expected_jpy is not None else None,
            "actual_jpy": str(row.actual_jpy) if row.actual_jpy is not None else None,
            "status": row.status, "owner": row.owner, "resolution_note": row.resolution_note,
            "resolution": {"action": resolution.action, "evidence_reference": resolution.evidence_reference,
                           "related_batch_id": resolution.related_batch_id, "actor": resolution.actor}
            if resolution else None,
            "task_id": task.id if task else None,
            "history": [{"from_state": item.from_state, "to_state": item.to_state,
                         "actor": item.actor, "reason": item.reason,
                         "occurred_at": item.occurred_at} for item in history]}


@router.get("/work-queue")
def work_queue(tenant_id: str, request: Request, db: Session = Depends(get_db),
               claims: dict = Depends(require_admin())):
    scoped_tenant(db, tenant_id)
    cases = db.scalars(select(ReconciliationCase).where(
        ReconciliationCase.tenant_id == tenant_id).order_by(ReconciliationCase.id)).all()
    tasks = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == tenant_id).order_by(WorkflowTask.created_at.desc())).all()
    result = {"tenant_id": tenant_id, "as_of": SNAPSHOT.date(),
              "cases": [case_json(db, row) for row in cases],
              "tasks": [{"id": row.id, "service": row.service, "employee_id": row.employee_id,
                         "operation_key": row.operation_key, "resource_id": row.resource_id,
                         "state": row.state, "reviewer_role": row.reviewer_role,
                         "evidence_reference": row.evidence_reference} for row in tasks]}
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service="provider_operations", outcome="permitted", reason="OK")
    return result


class CaseAction(BaseModel):
    action: str
    reason: str = Field(min_length=8, max_length=200)
    evidence_reference: str | None = Field(default=None, min_length=8, max_length=80)


@router.patch("/cases/{case_id}")
def review_case(tenant_id: str, case_id: str, body: CaseAction, request: Request,
                db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    scoped_tenant(db, tenant_id)
    row = db.get(ReconciliationCase, case_id)
    if not row or row.tenant_id != tenant_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Case is not available.")
    if body.action == "INVESTIGATE" and row.status == "OPEN":
        target = "INVESTIGATING"
    elif body.action == "WAIVE" and row.status in {"OPEN", "INVESTIGATING"}:
        if not body.evidence_reference:
            raise ApiError(422, "EVIDENCE_REQUIRED", "Waiver evidence is required.")
        target = "WAIVED"
    else:
        raise ApiError(409, "STATE_CONFLICT", "This case transition is not allowed.")
    previous = row.status
    row.status = target
    row.resolution_note = body.reason if target == "WAIVED" else row.resolution_note
    task = db.scalar(select(WorkflowTask).where(WorkflowTask.tenant_id == tenant_id,
                                                 WorkflowTask.resource_id == row.id))
    if not task:
        task = WorkflowTask(id=f"TASK-CASE-{row.id}", tenant_id=tenant_id, service=row.service,
                            employee_id=row.employee_id, operation_key="reconciliation_case",
                            resource_id=row.id, state=previous,
                            reviewer_role=row.owner, evidence_reference=row.source_reference,
                            created_at=SNAPSHOT, updated_at=SNAPSHOT)
        db.add(task)
    task.state = target
    task.updated_at = SNAPSHOT
    db.add(WorkflowTransition(task_id=task.id, from_state=previous, to_state=target,
                              actor=claims["sub"], reason=body.reason))
    if target == "WAIVED":
        db.add(CaseResolution(case_id=row.id, action="WAIVED",
                              evidence_reference=body.evidence_reference,
                              related_batch_id=None, reason=body.reason, actor=claims["sub"]))
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=row.employee_id, service=row.service, outcome="changed",
          reason=f"CASE_{target}")
    return case_json(db, row)


@router.get("/reports/service/{service}")
def service_report(tenant_id: str, service: str, request: Request,
                   as_of: date = Query(SNAPSHOT.date()),
                   db: Session = Depends(get_db), claims: dict = Depends(require_admin())):
    scoped_tenant(db, tenant_id)
    if service not in SERVICES:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Service is not available.")
    if as_of > SNAPSHOT.date():
        raise ApiError(422, "INVALID_DATE_RANGE", "Report date is beyond the available snapshot.")
    end = datetime.combine(as_of, time.max, tzinfo=timezone.utc)
    events = db.scalars(select(FinancialEvent).where(
        FinancialEvent.tenant_id == tenant_id, FinancialEvent.service == service,
        FinancialEvent.effective_at <= end).order_by(FinancialEvent.effective_at, FinancialEvent.id)).all()
    cases = db.scalars(select(ReconciliationCase).where(
        ReconciliationCase.tenant_id == tenant_id, ReconciliationCase.service == service)).all()
    totals: dict[str, str | int] = {
        "event_count": len(events),
        "journal_amount_jpy": f"{sum((Decimal(row.amount_jpy) for row in events), Decimal('0')):.2f}",
        "journal_quantity": f"{sum((Decimal(row.quantity) for row in events), Decimal('0')):.6f}",
        "open_case_count": sum(row.status in {"OPEN", "INVESTIGATING"} for row in cases),
    }
    if service == "equity":
        plan_ids = select(EquityPlanV2.id).where(EquityPlanV2.tenant_id == tenant_id)
        awards = db.scalars(select(EquityAward).where(
            EquityAward.plan_id.in_(plan_ids), EquityAward.grant_date <= as_of,
            EquityAward.state != "PROPOSED")).all()
        totals["issued_award_units"] = sum(row.granted_units for row in awards)
        totals["forfeited_award_units"] = sum(row.forfeited_units for row in awards)
        totals["award_count"] = len(awards)
    elif service == "wellness":
        content = db.scalars(select(WellnessContentV2).where(
            WellnessContentV2.tenant_id == tenant_id,
            WellnessContentV2.state == "PUBLISHED",
            WellnessContentV2.effective_date <= as_of,
            WellnessContentV2.review_expires_on >= as_of)).all()
        totals["current_published_content_count"] = len(content)
    result = {"tenant_id": tenant_id, "service": service, "as_of": as_of,
              "report_version": 1, "totals": totals,
              "source_references": sorted({row.source_reference for row in events})[:25],
              "case_references": [row.id for row in cases],
              "source_record_count": len(events)}
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=None, service=service, outcome="permitted", reason="REPORT_GENERATED")
    return result


@router.get("/reports/service/{service}/sources")
def service_report_sources(tenant_id: str, service: str, request: Request,
                           as_of: date = Query(SNAPSHOT.date()),
                           offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100),
                           db: Session = Depends(get_db), claims: dict = Depends(require_admin())):
    scoped_tenant(db, tenant_id)
    if service not in SERVICES:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Service is not available.")
    if as_of > SNAPSHOT.date():
        raise ApiError(422, "INVALID_DATE_RANGE", "Report date is beyond the available snapshot.")
    end = datetime.combine(as_of, time.max, tzinfo=timezone.utc)
    criteria = (FinancialEvent.tenant_id == tenant_id, FinancialEvent.service == service,
                FinancialEvent.effective_at <= end)
    total = db.scalar(select(func.count()).select_from(FinancialEvent).where(*criteria)) or 0
    events = db.scalars(select(FinancialEvent).where(*criteria).order_by(
        FinancialEvent.effective_at, FinancialEvent.id).offset(offset).limit(limit)).all()
    result = {"tenant_id": tenant_id, "service": service, "as_of": as_of,
              "offset": offset, "limit": limit, "total": total,
              "items": [{"id": row.id, "employee_id": row.employee_id,
                         "type": row.event_type, "source_reference": row.source_reference,
                         "correlation_id": row.correlation_id,
                         "effective_at": row.effective_at,
                         "amount_jpy": str(row.amount_jpy),
                         "quantity": str(row.quantity)} for row in events]}
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=None, service=service, outcome="permitted", reason="REPORT_SOURCES_VIEWED")
    return result


@router.get("/reports/participants/{employee_id}")
def participant_report(tenant_id: str, employee_id: str, request: Request,
                       service: str = Query(...), as_of: date = Query(SNAPSHOT.date()),
                       db: Session = Depends(get_db), claims: dict = Depends(require_admin())):
    scoped_tenant(db, tenant_id)
    employee = db.get(Employee, employee_id)
    if not employee or employee.tenant_id != tenant_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Participant is not available.")
    if service not in SERVICES or as_of > SNAPSHOT.date():
        raise ApiError(422, "INVALID_REQUEST", "Service or report date is invalid.")
    end = datetime.combine(as_of, time.max, tzinfo=timezone.utc)
    events = db.scalars(select(FinancialEvent).where(
        FinancialEvent.tenant_id == tenant_id,
        FinancialEvent.employee_id == employee_id,
        FinancialEvent.service == service,
        FinancialEvent.effective_at <= end).order_by(FinancialEvent.effective_at, FinancialEvent.id)).all()
    statements = db.scalars(select(OperationalStatement).where(
        OperationalStatement.tenant_id == tenant_id,
        OperationalStatement.employee_id == employee_id,
        OperationalStatement.service == service,
        OperationalStatement.as_of <= as_of)).all()
    result = {"tenant_id": tenant_id, "employee_id": employee_id,
              "service": service, "as_of": as_of,
              "journal_amount_jpy": f"{sum((Decimal(row.amount_jpy) for row in events), Decimal('0')):.2f}",
              "journal_quantity": f"{sum((Decimal(row.quantity) for row in events), Decimal('0')):.6f}",
              "events": [{"id": row.id, "type": row.event_type,
                          "source_reference": row.source_reference,
                          "correlation_id": row.correlation_id,
                          "effective_at": row.effective_at,
                          "amount_jpy": str(row.amount_jpy),
                          "quantity": str(row.quantity)} for row in events],
              "statement_references": [row.id for row in statements]}
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=employee_id, service=service,
          outcome="permitted", reason="PARTICIPANT_REPORT_GENERATED")
    return result
