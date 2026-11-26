"""Equity award lifecycle and read/draft API."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Employee
from .security import ApiError, audit, require_admin, require_client
from .v2_models import (EquityAward, EquityExerciseDraft, EquityPlanV2, EquityRelease,
                        EquityTranche, OperationalStatement, ReconciliationCase)

router = APIRouter(prefix="/api/v2", tags=["Equity compensation v2"])
AS_OF = date(2026, 11, 26)


def client_audit(db, request, claims, outcome="permitted", reason="OK"):
    request.state.principal_scopes = ",".join(claims.get("scopes") or [])
    audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"],
          employee_id=claims["employee_id"], service="equity", outcome=outcome, reason=reason)


def plan_for_tenant(db, tenant_id):
    plan = db.scalar(select(EquityPlanV2).where(EquityPlanV2.tenant_id == tenant_id))
    if not plan:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Equity plan is not available.")
    return plan


def tranches(db, award_id):
    return list(db.scalars(select(EquityTranche).where(EquityTranche.award_id == award_id)
                           .order_by(EquityTranche.vest_date)))


def award_json(db, award):
    items = tranches(db, award.id)
    scheduled = sum(x.units for x in items if x.state == "SCHEDULED")
    vested = sum(x.units for x in items if x.state == "VESTED")
    forfeited = award.forfeited_units + sum(x.units for x in items if x.state == "FORFEITED")
    released = award.released_units if award.award_type == "RSU" else award.exercised_units
    unreleased = vested - released
    reconciled = scheduled + unreleased + released + forfeited == award.granted_units
    exercisable = max(0, unreleased) if award.award_type == "Option" and (
        award.expiry_date is None or award.expiry_date >= AS_OF) and award.state == "ACTIVE" else 0
    return {"id": award.id, "plan_id": award.plan_id, "employee_id": award.employee_id,
            "award_type": award.award_type, "state": award.state,
            "grant_date": award.grant_date, "granted_units": award.granted_units,
            "scheduled_unvested_units": scheduled, "vested_unreleased_units": unreleased,
            "released_units": award.released_units, "exercised_units": award.exercised_units,
            "forfeited_units": forfeited, "currently_exercisable_units": exercisable,
            "strike_jpy": str(award.strike_jpy) if award.strike_jpy is not None else None,
            "expiry_date": award.expiry_date, "reconciled": reconciled,
            "tranches": [{"id": x.id, "vest_date": x.vest_date, "units": x.units,
                          "state": x.state} for x in items]}


def own_awards(db, claims):
    plan = plan_for_tenant(db, claims["tenant_id"])
    return list(db.scalars(select(EquityAward).where(EquityAward.plan_id == plan.id,
                                                     EquityAward.employee_id == claims["employee_id"])
                           .order_by(EquityAward.grant_date)))


@router.get("/client/me/equity/grants")
def client_grants(request: Request, db: Session = Depends(get_db),
                  claims: dict = Depends(require_client("equity"))):
    rows = [award_json(db, x) for x in own_awards(db, claims) if x.state in {"ISSUED", "ACTIVE"}]
    client_audit(db, request, claims)
    return {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"],
            "as_of": AS_OF, "grants": rows}


@router.get("/client/me/equity/grants/{grant_id}")
def client_grant(grant_id: str, request: Request, db: Session = Depends(get_db),
                 claims: dict = Depends(require_client("equity"))):
    row = next((x for x in own_awards(db, claims) if x.id == grant_id and x.state in {"ISSUED", "ACTIVE"}), None)
    if not row:
        client_audit(db, request, claims, "denied", "RESOURCE_NOT_ACCESSIBLE")
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Grant is not available.")
    result = award_json(db, row)
    client_audit(db, request, claims)
    return result


@router.get("/client/me/equity/vesting")
def client_vesting(request: Request, db: Session = Depends(get_db),
                   claims: dict = Depends(require_client("equity"))):
    rows = [award_json(db, x) for x in own_awards(db, claims) if x.state in {"ISSUED", "ACTIVE"}]
    client_audit(db, request, claims)
    return {"as_of": AS_OF, "vesting": [{"grant_id": x["id"], **t}
                                      for x in rows for t in x["tranches"]]}


@router.get("/client/me/equity/options")
def client_options(request: Request, db: Session = Depends(get_db),
                   claims: dict = Depends(require_client("equity"))):
    rows = [award_json(db, x) for x in own_awards(db, claims)
            if x.award_type == "Option" and x.state in {"ISSUED", "ACTIVE"}]
    client_audit(db, request, claims)
    return {"as_of": AS_OF, "options": rows}


@router.get("/client/me/equity/releases")
def client_releases(request: Request, db: Session = Depends(get_db),
                    claims: dict = Depends(require_client("equity"))):
    plan = plan_for_tenant(db, claims["tenant_id"])
    rows = db.scalars(select(EquityRelease).join(EquityAward, EquityAward.id == EquityRelease.award_id)
                      .where(EquityRelease.employee_id == claims["employee_id"],
                             EquityAward.plan_id == plan.id)).all()
    client_audit(db, request, claims)
    return {"as_of": AS_OF, "releases": [release_json(x) for x in rows]}


def release_json(row):
    return {"id": row.id, "grant_id": row.award_id, "units": row.units,
            "withholding_units": row.withholding_units, "state": row.state,
            "custody_confirmation": row.custody_confirmation}


@router.get("/client/me/equity/statement")
def client_statement(request: Request, db: Session = Depends(get_db),
                     claims: dict = Depends(require_client("equity"))):
    rows = db.scalars(select(OperationalStatement).where(
        OperationalStatement.tenant_id == claims["tenant_id"],
        OperationalStatement.employee_id == claims["employee_id"],
        OperationalStatement.service == "equity")).all()
    client_audit(db, request, claims)
    return {"as_of": AS_OF, "statements": [{"id": x.id, "period": x.period,
                                            "grant_id": x.source_reference} for x in rows]}


class ExerciseInput(BaseModel):
    grant_id: str
    units: int = Field(gt=0)


@router.post("/client/me/equity/exercise-drafts", status_code=201)
def client_exercise_draft(body: ExerciseInput, request: Request,
                          idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=80),
                          db: Session = Depends(get_db),
                          claims: dict = Depends(require_client("equity", "draft"))):
    existing = db.scalar(select(EquityExerciseDraft).where(
        EquityExerciseDraft.employee_id == claims["employee_id"],
        EquityExerciseDraft.idempotency_key == idempotency_key))
    if existing:
        if existing.award_id != body.grant_id or existing.units != body.units:
            client_audit(db, request, claims, "denied", "DUPLICATE_REQUEST")
            raise ApiError(409, "DUPLICATE_REQUEST", "Request key was already used for a different draft.")
        client_audit(db, request, claims)
        return draft_json(existing)
    row = next((x for x in own_awards(db, claims) if x.id == body.grant_id), None)
    if not row or row.award_type != "Option" or row.state != "ACTIVE":
        client_audit(db, request, claims, "denied", "OPTION_NOT_ELIGIBLE")
        raise ApiError(422, "OPTION_NOT_ELIGIBLE", "This award is not eligible for an exercise draft.")
    detail = award_json(db, row)
    if body.units > detail["currently_exercisable_units"]:
        client_audit(db, request, claims, "denied", "UNITS_UNAVAILABLE")
        raise ApiError(422, "UNITS_UNAVAILABLE", "Requested units exceed exercisable units.")
    draft = EquityExerciseDraft(id="EXD-" + uuid.uuid4().hex[:12].upper(), award_id=row.id,
                                employee_id=row.employee_id, units=body.units,
                                idempotency_key=idempotency_key, state="DRAFT")
    db.add(draft)
    client_audit(db, request, claims, "changed", "EXERCISE_DRAFT_CREATED")
    return draft_json(draft)


def draft_json(row):
    return {"id": row.id, "grant_id": row.award_id, "units": row.units, "state": row.state,
            "effect": "DRAFT_ONLY"}


class ReviewInput(BaseModel):
    state: str
    reason: str = Field(min_length=3, max_length=200)


@router.patch("/admin/tenants/{tenant_id}/equity/releases/{release_id}")
def review_release(tenant_id: str, release_id: str, body: ReviewInput, request: Request,
                   db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    release = db.get(EquityRelease, release_id)
    plan = plan_for_tenant(db, tenant_id)
    award = db.get(EquityAward, release.award_id) if release else None
    if not award or award.plan_id != plan.id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Release is not available.")
    if (release.state, body.state) not in {("PREPARED", "VERIFIED"), ("VERIFIED", "APPROVED"),
                                           ("APPROVED", "SIMULATED_RELEASED")}:
        raise ApiError(409, "STATE_CONFLICT", "Release state change is not allowed.")
    if body.state == "SIMULATED_RELEASED":
        available = award_json(db, award)["vested_unreleased_units"]
        if release.units > available:
            raise ApiError(409, "UNITS_UNAVAILABLE", "Vested unreleased units are insufficient.")
        award.released_units += release.units
    release.state = body.state
    request.state.operation = "review_equity_release"
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=award.employee_id, service="equity", outcome="changed", reason=body.state)
    return release_json(release)


@router.patch("/admin/tenants/{tenant_id}/equity/grants/{grant_id}")
def review_grant(tenant_id: str, grant_id: str, body: ReviewInput, request: Request,
                 db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    plan = plan_for_tenant(db, tenant_id)
    row = db.get(EquityAward, grant_id)
    if not row or row.plan_id != plan.id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Grant is not available.")
    if (row.state, body.state) not in {("PROPOSED", "APPROVED"), ("APPROVED", "ISSUED"),
                                       ("ISSUED", "ACTIVE")}:
        raise ApiError(409, "STATE_CONFLICT", "Grant state change is not allowed.")
    if body.state == "ISSUED":
        used = sum(x.granted_units for x in db.scalars(select(EquityAward).where(
            EquityAward.plan_id == plan.id, EquityAward.state.in_(["ISSUED", "ACTIVE"]))))
        if used + row.granted_units > plan.authorized_units:
            raise ApiError(409, "RESERVE_EXCEEDED", "Plan share reserve would be exceeded.")
    row.state = body.state
    request.state.operation = "review_equity_grant"
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=row.employee_id, service="equity", outcome="changed", reason=body.state)
    return award_json(db, row)


@router.get("/admin/tenants/{tenant_id}/equity/operations")
def admin_equity_operations(tenant_id: str, request: Request, db: Session = Depends(get_db),
                            claims: dict = Depends(require_admin())):
    plan = plan_for_tenant(db, tenant_id)
    awards = list(db.scalars(select(EquityAward).where(EquityAward.plan_id == plan.id)))
    issued = sum(x.granted_units for x in awards if x.state in {"ISSUED", "ACTIVE"})
    releases = list(db.scalars(select(EquityRelease).join(EquityAward,
        EquityAward.id == EquityRelease.award_id).where(EquityAward.plan_id == plan.id)))
    cases = list(db.scalars(select(ReconciliationCase).where(
        ReconciliationCase.tenant_id == tenant_id, ReconciliationCase.service == "equity")))
    request.state.operation = "view_equity_operations"
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=None, service="equity", outcome="permitted", reason="OK")
    return {"tenant_id": tenant_id, "as_of": AS_OF,
            "plan": {"id": plan.id, "name": plan.name, "status": plan.status,
                     "authorized_units": plan.authorized_units, "issued_units": issued,
                     "remaining_units": plan.authorized_units - issued},
            "grants": [award_json(db, x) for x in awards],
            "releases": [release_json(x) for x in releases],
            "exceptions": [{"id": x.id, "employee_id": x.employee_id,
                            "break_type": x.break_type, "status": x.status} for x in cases]}
