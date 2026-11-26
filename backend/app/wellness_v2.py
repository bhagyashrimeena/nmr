"""Approved education, tenant rules, learning records and reproducible calculators."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Employee, TenantServiceSetting, WellnessProgress
from .security import ApiError, audit, require_admin, require_client
from .v2_models import WellnessBenefitAccess, WellnessBenefitRule, WellnessContentV2, WellnessSeminar

router = APIRouter(prefix="/api/v2", tags=["Financial wellness v2"])
AS_OF = date(2026, 11, 26)


def client_audit(db, request, claims, outcome="permitted", reason="OK"):
    request.state.principal_scopes = ",".join(claims.get("scopes") or [])
    audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"],
          employee_id=claims["employee_id"], service="wellness", outcome=outcome, reason=reason)


def content_json(row):
    return {"id": row.id, "title": row.title, "category": row.category,
            "language": row.language, "body": row.body, "state": row.state,
            "source_reference": row.source_reference, "effective_date": row.effective_date,
            "review_expires_on": row.review_expires_on, "revision": row.revision}


def published(row):
    return row.state == "PUBLISHED" and row.effective_date <= AS_OF <= row.review_expires_on


@router.get("/client/wellness/education")
def client_education(request: Request, category: str | None = Query(None, max_length=40),
                     search: str | None = Query(None, max_length=80),
                     db: Session = Depends(get_db), claims: dict = Depends(require_client("wellness"))):
    rows = list(db.scalars(select(WellnessContentV2).where(
        WellnessContentV2.tenant_id == claims["tenant_id"])))
    items = [content_json(x) for x in rows if published(x) and
             (category is None or x.category == category) and
             (search is None or search.lower() in (x.title + " " + x.body).lower())]
    client_audit(db, request, claims)
    return {"as_of": AS_OF, "items": items}


def resolve_benefit(db: Session, claims: dict, benefit_key: str):
    rule = db.scalar(select(WellnessBenefitRule).where(
        WellnessBenefitRule.tenant_id == claims["tenant_id"],
        WellnessBenefitRule.benefit_key == benefit_key,
        WellnessBenefitRule.effective_date <= AS_OF,
        WellnessBenefitRule.review_expires_on >= AS_OF))
    if not rule:
        raise ApiError(404, "BENEFIT_RULE_NOT_AVAILABLE", "No current rule is available for this benefit.")
    policy = db.get(WellnessBenefitAccess, rule.id)
    if not policy:
        raise ApiError(404, "BENEFIT_RULE_NOT_AVAILABLE", "No disclosure policy is available for this benefit.")
    service_setting = db.scalar(select(TenantServiceSetting).where(
        TenantServiceSetting.tenant_id == claims["tenant_id"],
        TenantServiceSetting.service == policy.underlying_service))
    if not service_setting or not service_setting.enabled:
        raise ApiError(403, "SERVICE_ACCESS_DISABLED", "Access to this benefit service is disabled.")
    employee = db.get(Employee, claims["employee_id"])
    if policy.underlying_service not in employee.allowed_services.split(","):
        raise ApiError(403, "INSUFFICIENT_PERMISSIONS", "This benefit is not available to the employee.")
    return {"benefit_key": benefit_key, "explanation": rule.rule_text,
            "source_reference": rule.source_reference, "effective_date": rule.effective_date,
            "review_expires_on": rule.review_expires_on}


def audited_benefits(db: Session, request: Request, claims: dict, keys: list[str]):
    try:
        items = [resolve_benefit(db, claims, key) for key in keys]
    except ApiError as exc:
        client_audit(db, request, claims, "denied", exc.code)
        raise
    client_audit(db, request, claims)
    return items


@router.get("/client/wellness/benefits/{benefit_key}")
def client_benefit(benefit_key: str, request: Request, db: Session = Depends(get_db),
                   claims: dict = Depends(require_client("wellness"))):
    return audited_benefits(db, request, claims, [benefit_key])[0]


@router.get("/client/wellness/benefit-comparison")
def client_benefit_comparison(request: Request, db: Session = Depends(get_db),
                              claims: dict = Depends(require_client("wellness"))):
    keys = ["shareholding_incentive", "corporate_pension_contributions"]
    return {"as_of": AS_OF, "benefits": audited_benefits(db, request, claims, keys),
            "comparison": "The shareholding plan purchases company shares; the corporate pension invests contributions through its fund menu. Account values and rules are separate."}


@router.get("/client/wellness/progress")
def client_progress(request: Request, db: Session = Depends(get_db),
                    claims: dict = Depends(require_client("wellness"))):
    rows = list(db.scalars(select(WellnessProgress).where(
        WellnessProgress.employee_id == claims["employee_id"])))
    client_audit(db, request, claims)
    return {"employee_id": claims["employee_id"],
            "progress": [{"resource_id": x.resource_id, "status": x.status} for x in rows]}


@router.get("/client/wellness/seminars")
def client_seminars(request: Request, db: Session = Depends(get_db),
                    claims: dict = Depends(require_client("wellness"))):
    rows = list(db.scalars(select(WellnessSeminar).where(
        WellnessSeminar.tenant_id == claims["tenant_id"])))
    client_audit(db, request, claims)
    return {"seminars": [{"id": x.id, "title": x.title, "starts_at": x.starts_at,
                          "capacity": x.capacity, "registrations": x.registrations,
                          "status": x.status} for x in rows]}


@router.get("/client/wellness/calculators/monthly-savings")
def client_savings(request: Request, monthly_jpy: Decimal = Query(Decimal("15000"), ge=0, le=1000000),
                   months: int = Query(120, ge=1, le=480),
                   annual_rate_percent: Decimal = Query(Decimal("0"), ge=0, le=12),
                   db: Session = Depends(get_db), claims: dict = Depends(require_client("wellness"))):
    monthly_rate = annual_rate_percent / Decimal("1200")
    balance = Decimal("0")
    for _ in range(months):
        balance = balance * (1 + monthly_rate) + monthly_jpy
    balance = balance.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    contributed = (monthly_jpy * months).quantize(Decimal("0.01"))
    client_audit(db, request, claims)
    return {"formula_id": "MONTHLY_END_OF_PERIOD_COMPOUND_V1", "currency": "JPY",
            "inputs": {"monthly_jpy": str(monthly_jpy), "months": months,
                       "annual_rate_percent": str(annual_rate_percent)},
            "monthly_rate": str(monthly_rate), "contributed_jpy": str(contributed),
            "future_value_jpy": str(balance), "growth_jpy": str(balance - contributed),
            "disclosure": "Projection uses a constant annual rate and monthly end-of-period contributions. Results are not a guarantee or a product recommendation."}


class ReviewInput(BaseModel):
    state: str
    reason: str = Field(min_length=3, max_length=200)


@router.patch("/admin/tenants/{tenant_id}/wellness/content/{content_id}")
def review_content(tenant_id: str, content_id: str, body: ReviewInput, request: Request,
                   db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    row = db.get(WellnessContentV2, content_id)
    if not row or row.tenant_id != tenant_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Content item is not available.")
    if (row.state, body.state) not in {("DRAFT", "IN_REVIEW"), ("IN_REVIEW", "APPROVED"),
                                       ("APPROVED", "PUBLISHED"), ("PUBLISHED", "ARCHIVED")}:
        raise ApiError(409, "STATE_CONFLICT", "Content state change is not allowed.")
    if body.state == "PUBLISHED" and row.review_expires_on < AS_OF:
        raise ApiError(409, "REVIEW_EXPIRED", "Content review has expired.")
    row.state = body.state
    request.state.operation = "review_wellness_content"
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=None, service="wellness", outcome="changed", reason=body.state)
    return content_json(row)


@router.get("/admin/tenants/{tenant_id}/wellness/operations")
def admin_wellness_operations(tenant_id: str, request: Request, db: Session = Depends(get_db),
                              claims: dict = Depends(require_admin())):
    items = list(db.scalars(select(WellnessContentV2).where(WellnessContentV2.tenant_id == tenant_id)))
    rules = list(db.scalars(select(WellnessBenefitRule).where(WellnessBenefitRule.tenant_id == tenant_id)))
    seminars = list(db.scalars(select(WellnessSeminar).where(WellnessSeminar.tenant_id == tenant_id)))
    request.state.operation = "view_wellness_operations"
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=None, service="wellness", outcome="permitted", reason="OK")
    return {"tenant_id": tenant_id, "as_of": AS_OF,
            "content": [content_json(x) for x in items],
            "benefit_rules": [{"id": x.id, "benefit_key": x.benefit_key,
                               "underlying_service": db.get(WellnessBenefitAccess, x.id).underlying_service
                               if db.get(WellnessBenefitAccess, x.id) else None,
                               "rule_text": x.rule_text, "source_reference": x.source_reference,
                               "effective_date": x.effective_date, "review_expires_on": x.review_expires_on} for x in rules],
            "seminars": [{"id": x.id, "title": x.title, "starts_at": x.starts_at,
                          "capacity": x.capacity, "registrations": x.registrations,
                          "status": x.status} for x in seminars]}
