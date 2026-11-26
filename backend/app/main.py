import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalog import SERVICES as CATALOG
from .db import Base, SessionLocal, engine, get_db
from .details import SERVICES, growth_projection, wellness_summary
from .models import AccessChange, AuditEvent, Employee, McpSetting, Tenant, TenantServiceSetting, WellnessProgress, WellnessResource, utc_now
from .schemas import (AccessChangeItem, AdminLogin, CustodyResponse, EquityResponse, ErrorResponse,
                      McpPatch, McpResponse, PensionResponse, ProjectionResponse, StockResponse,
                      TokenResponse, WellnessProgressPatch, WellnessResponse)
from .security import ApiError, audit, mint_token, require_admin, require_client, verify_admin_password
from .seed import AS_OF, seed

logger = logging.getLogger("nmr.api")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="NMR Workplace Finance Provider API", version="1.0.0",
              description="Fictional, read-only workplace finance demonstration API. No real customer data or transactions.",
              lifespan=lifespan)
origins = [x.strip() for x in os.getenv("NMR_CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
                   expose_headers=["X-Request-ID"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("x-request-id", "")
    request.state.request_id = supplied if re.fullmatch(r"[A-Za-z0-9._-]{1,80}", supplied) else str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    logger.info(json.dumps({"request_id": request.state.request_id, "method": request.method,
                            "path": request.url.path, "status": response.status_code}))
    return response


def error_response(request: Request, status: int, code: str, message: str):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message,
                                                               "request_id": request.state.request_id}})


@app.exception_handler(ApiError)
async def api_error(request: Request, exc: ApiError):
    return error_response(request, exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, _exc: RequestValidationError):
    return error_response(request, 422, "INVALID_REQUEST", "The request does not match the API contract.")


ERRORS = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "synthetic_demo": True}


@app.post("/api/v1/auth/admin-token", response_model=TokenResponse, tags=["Authentication"], responses=ERRORS)
def admin_token(body: AdminLogin):
    if not verify_admin_password(body.username, body.password):
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid administrator credentials.")
    return {"access_token": mint_token(sub="nmr-admin", role="admin", scopes=["admin:read", "admin:write"], minutes=60),
            "token_type": "bearer", "expires_in": 3600}


def client_payload(request: Request, db: Session, claims: dict, service: str):
    employee_id = claims["employee_id"]
    result = SERVICES[service](db, employee_id)
    if result is None:
        audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"], employee_id=employee_id,
              service=service, outcome="denied", reason="RECORD_NOT_FOUND")
        raise ApiError(404, "RECORD_NOT_FOUND", "No service record is available for this employee.")
    audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"], employee_id=employee_id,
          service=service, outcome="permitted", reason="OK")
    return {"tenant_id": claims["tenant_id"], "employee_id": employee_id, **result}


@app.get("/api/v1/client/me/stock-ownership", response_model=StockResponse, tags=["Client · Stock ownership"], responses=ERRORS)
def client_stock(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("stock"))):
    return client_payload(request, db, claims, "stock")


@app.get("/api/v1/client/me/pension", response_model=PensionResponse, tags=["Client · Pension"], responses=ERRORS)
def client_pension(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("pension"))):
    return client_payload(request, db, claims, "pension")


@app.get("/api/v1/client/wellness/resources", response_model=WellnessResponse, tags=["Client · Wellness"], responses=ERRORS)
def client_wellness(request: Request, topic: str | None = Query(default=None, max_length=50),
                    search: str | None = Query(default=None, max_length=80),
                    db: Session = Depends(get_db), claims: dict = Depends(require_client("wellness"))):
    result = {"tenant_id": claims["tenant_id"], "employee_id": claims["employee_id"], "as_of": AS_OF,
              **wellness_summary(db, claims["employee_id"], topic, search)}
    audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"], employee_id=claims["employee_id"],
          service="wellness", outcome="permitted", reason="OK")
    return result


@app.get("/api/v1/client/me/custody", response_model=CustodyResponse, tags=["Client · Custody"], responses=ERRORS)
def client_custody(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("custody"))):
    return client_payload(request, db, claims, "custody")


@app.get("/api/v1/client/me/equity-compensation", response_model=EquityResponse, tags=["Client · Equity compensation"], responses=ERRORS)
def client_equity(request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_client("equity"))):
    return client_payload(request, db, claims, "equity")


def projection_result(tenant_id: str, employee_id: str, purpose: str,
                      starting_jpy: int, monthly_jpy: int, years: int, annual_return_pct: Decimal):
    return {"tenant_id": tenant_id, "employee_id": employee_id, "as_of": AS_OF,
            "currency": "JPY", "purpose": purpose,
            "projection": growth_projection(starting_jpy, monthly_jpy, years, annual_return_pct)}


@app.get("/api/v1/client/wellness/savings-projection", response_model=ProjectionResponse,
         tags=["Client · Wellness"], responses=ERRORS)
def client_savings_projection(request: Request, monthly_jpy: int = Query(15000, ge=0, le=1_000_000),
                              years: int = Query(10, ge=1, le=40),
                              annual_return_pct: Decimal = Query(Decimal("0"), ge=0, le=12),
                              db: Session = Depends(get_db), claims: dict = Depends(require_client("wellness"))):
    result = projection_result(claims["tenant_id"], claims["employee_id"], "monthly_savings",
                               0, monthly_jpy, years, annual_return_pct)
    audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"], employee_id=claims["employee_id"],
          service="wellness", outcome="permitted", reason="OK")
    return result


@app.get("/api/v1/client/me/pension/projection", response_model=ProjectionResponse,
         tags=["Client · Pension"], responses=ERRORS)
def client_pension_projection(request: Request, years: int = Query(20, ge=1, le=40),
                              annual_return_pct: Decimal = Query(Decimal("4"), ge=0, le=12),
                              monthly_contribution_jpy: int | None = Query(None, ge=0, le=1_000_000),
                              db: Session = Depends(get_db), claims: dict = Depends(require_client("pension"))):
    pension = SERVICES["pension"](db, claims["employee_id"])
    if pension is None:
        audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"], employee_id=claims["employee_id"],
              service="pension", outcome="denied", reason="RECORD_NOT_FOUND")
        raise ApiError(404, "RECORD_NOT_FOUND", "No pension record is available for this employee.")
    monthly = monthly_contribution_jpy if monthly_contribution_jpy is not None else pension["projection"]["monthly_contribution_jpy"]
    result = projection_result(claims["tenant_id"], claims["employee_id"], "retirement_balance",
                               pension["balance_jpy"], monthly, years, annual_return_pct)
    audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"], employee_id=claims["employee_id"],
          service="pension", outcome="permitted", reason="OK")
    return result


def tenant_or_404(db: Session, tenant_id: str):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise ApiError(404, "TENANT_NOT_FOUND", "Tenant is not available.")
    return tenant


@app.get("/api/v1/admin/tenants", tags=["Admin"], responses=ERRORS)
def admin_tenants(db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    tenants = db.scalars(select(Tenant).order_by(Tenant.id)).all()
    return [{"id": t.id, "name": t.name, "fictional_demo_flag": t.fictional_demo_flag,
             "mcp_enabled": bool(db.get(McpSetting, t.id).enabled)} for t in tenants]


@app.get("/api/v1/admin/tenants/{tenant_id}/overview", tags=["Admin"], responses=ERRORS)
def admin_overview(tenant_id: str, db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    tenant = tenant_or_404(db, tenant_id)
    setting = db.get(McpSetting, tenant_id)
    count = db.scalar(select(func.count()).select_from(Employee).where(Employee.tenant_id == tenant_id))
    recent = db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.id.desc()).limit(5)).all()
    service_settings = db.scalars(select(TenantServiceSetting).where(TenantServiceSetting.tenant_id == tenant_id)).all()
    configured = sum(item.enabled for item in service_settings)
    return {"tenant_id": tenant.id, "name": tenant.name, "synthetic_demo": True, "as_of": AS_OF,
            "employee_count": count, "mcp_enabled": bool(setting and setting.enabled),
            "operational_service_count": len(CATALOG), "configured_enabled_services": configured,
            "effective_enabled_services": configured if setting and setting.enabled else 0,
            "recent_activity": [audit_json(event) for event in recent]}


@app.get("/api/v1/admin/tenants/{tenant_id}/employees", tags=["Admin"], responses=ERRORS)
def admin_employees(tenant_id: str, db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    tenant_or_404(db, tenant_id)
    employees = db.scalars(select(Employee).where(Employee.tenant_id == tenant_id).order_by(Employee.id)).all()
    return [{"id": e.id, "display_name": e.display_name, "active": e.active,
             "allowed_services": e.allowed_services.split(",")} for e in employees]


@app.get("/api/v1/admin/tenants/{tenant_id}/employees/{employee_id}/service-summary", tags=["Admin"], responses=ERRORS)
def admin_service_summary(tenant_id: str, employee_id: str, db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    tenant_or_404(db, tenant_id)
    employee = db.get(Employee, employee_id)
    if not employee or employee.tenant_id != tenant_id:
        raise ApiError(404, "EMPLOYEE_NOT_FOUND", "Employee record is not available.")
    return {"tenant_id": tenant_id, "employee_id": employee_id, "display_name": employee.display_name,
            "as_of": AS_OF, "stock": SERVICES["stock"](db, employee_id),
            "pension": SERVICES["pension"](db, employee_id),
            "wellness": wellness_summary(db, employee_id),
            "custody": SERVICES["custody"](db, employee_id),
            "equity": SERVICES["equity"](db, employee_id)}


def employee_for_tenant(db: Session, tenant_id: str, employee_id: str):
    tenant_or_404(db, tenant_id)
    employee = db.get(Employee, employee_id)
    if not employee or employee.tenant_id != tenant_id:
        raise ApiError(404, "EMPLOYEE_NOT_FOUND", "Employee record is not available.")
    return employee


@app.get("/api/v1/admin/tenants/{tenant_id}/employees/{employee_id}/wellness/resources",
         tags=["Admin"], responses=ERRORS)
def admin_wellness(tenant_id: str, employee_id: str,
                   topic: str | None = Query(None, max_length=50), search: str | None = Query(None, max_length=80),
                   db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    employee_for_tenant(db, tenant_id, employee_id)
    return wellness_summary(db, employee_id, topic, search)


@app.patch("/api/v1/admin/tenants/{tenant_id}/employees/{employee_id}/wellness/progress/{resource_id}",
           tags=["Admin"], responses=ERRORS)
def admin_wellness_progress(tenant_id: str, employee_id: str, resource_id: str,
                            body: WellnessProgressPatch, request: Request,
                            db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    employee_for_tenant(db, tenant_id, employee_id)
    if not db.get(WellnessResource, resource_id):
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Wellness resource is not available.")
    progress = db.scalar(select(WellnessProgress).where(WellnessProgress.employee_id == employee_id,
                                                       WellnessProgress.resource_id == resource_id))
    if progress:
        progress.status = body.status
    else:
        db.add(WellnessProgress(employee_id=employee_id, resource_id=resource_id, status=body.status))
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=employee_id,
          service="wellness", outcome="changed", reason=f"PROGRESS_{body.status.upper()}:{resource_id}")
    return wellness_summary(db, employee_id)


@app.get("/api/v1/admin/tenants/{tenant_id}/employees/{employee_id}/wellness/savings-projection",
         response_model=ProjectionResponse, tags=["Admin"], responses=ERRORS)
def admin_savings_projection(tenant_id: str, employee_id: str,
                             monthly_jpy: int = Query(15000, ge=0, le=1_000_000),
                             years: int = Query(10, ge=1, le=40),
                             annual_return_pct: Decimal = Query(Decimal("0"), ge=0, le=12),
                             db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    employee_for_tenant(db, tenant_id, employee_id)
    return projection_result(tenant_id, employee_id, "monthly_savings", 0, monthly_jpy, years, annual_return_pct)


@app.get("/api/v1/admin/tenants/{tenant_id}/employees/{employee_id}/pension/projection",
         response_model=ProjectionResponse, tags=["Admin"], responses=ERRORS)
def admin_pension_projection(tenant_id: str, employee_id: str, years: int = Query(20, ge=1, le=40),
                             annual_return_pct: Decimal = Query(Decimal("4"), ge=0, le=12),
                             monthly_contribution_jpy: int | None = Query(None, ge=0, le=1_000_000),
                             db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    employee_for_tenant(db, tenant_id, employee_id)
    pension = SERVICES["pension"](db, employee_id)
    if not pension:
        raise ApiError(404, "RECORD_NOT_FOUND", "No pension record is available for this employee.")
    monthly = monthly_contribution_jpy if monthly_contribution_jpy is not None else pension["projection"]["monthly_contribution_jpy"]
    return projection_result(tenant_id, employee_id, "retirement_balance", pension["balance_jpy"], monthly, years, annual_return_pct)


def setting_json(db: Session, setting: McpSetting):
    rows = {row.service: row for row in db.scalars(select(TenantServiceSetting).where(TenantServiceSetting.tenant_id == setting.tenant_id))}
    services = [{"service": key, **meta, "enabled": bool(rows.get(key) and rows[key].enabled),
                 "effective_enabled": bool(setting.enabled and rows.get(key) and rows[key].enabled),
                 "changed_by": rows[key].changed_by if key in rows else "missing",
                 "changed_at": rows[key].changed_at if key in rows else setting.changed_at,
                 "reason": rows[key].reason if key in rows else "No setting"} for key, meta in CATALOG.items()]
    return {"tenant_id": setting.tenant_id, "enabled": setting.enabled, "changed_by": setting.changed_by,
            "changed_at": setting.changed_at, "reason": setting.reason,
            "services": services, "effective_service_count": sum(row["effective_enabled"] for row in services)}


@app.get("/api/v1/admin/tenants/{tenant_id}/mcp-access", response_model=McpResponse, tags=["Admin"], responses=ERRORS)
def admin_get_mcp(tenant_id: str, db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    tenant_or_404(db, tenant_id)
    return setting_json(db, db.get(McpSetting, tenant_id))


@app.patch("/api/v1/admin/tenants/{tenant_id}/mcp-access", response_model=McpResponse, tags=["Admin"], responses=ERRORS)
def admin_patch_mcp(tenant_id: str, body: McpPatch, request: Request, db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    tenant_or_404(db, tenant_id)
    setting = db.get(McpSetting, tenant_id)
    if setting.enabled == body.enabled:
        return setting_json(db, setting)
    previous = setting.enabled
    setting.enabled = body.enabled
    setting.changed_by = claims["sub"]
    setting.changed_at = utc_now()
    setting.reason = body.reason
    db.add(AccessChange(request_id=request.state.request_id, actor=claims["sub"], tenant_id=tenant_id,
                        service="master", previous_enabled=previous, new_enabled=body.enabled, reason=body.reason))
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service="mcp-access", outcome="changed", reason="ENABLED" if body.enabled else "DISABLED")
    db.refresh(setting)
    return setting_json(db, setting)


@app.patch("/api/v1/admin/tenants/{tenant_id}/service-access/{service}", response_model=McpResponse,
           tags=["Admin"], responses=ERRORS)
def admin_patch_service(tenant_id: str, service: str, body: McpPatch, request: Request,
                        db: Session = Depends(get_db), claims: dict = Depends(require_admin(write=True))):
    tenant_or_404(db, tenant_id)
    if service not in CATALOG:
        raise ApiError(404, "SERVICE_NOT_FOUND", "Service is not available.")
    setting = db.scalar(select(TenantServiceSetting).where(TenantServiceSetting.tenant_id == tenant_id,
                                                            TenantServiceSetting.service == service))
    if not setting:
        raise ApiError(404, "SERVICE_NOT_FOUND", "Service setting is not available.")
    if setting.enabled == body.enabled:
        return setting_json(db, db.get(McpSetting, tenant_id))
    previous = setting.enabled
    setting.enabled = body.enabled
    setting.changed_by = claims["sub"]
    setting.changed_at = utc_now()
    setting.reason = body.reason
    db.add(AccessChange(request_id=request.state.request_id, actor=claims["sub"], tenant_id=tenant_id,
                        service=service, previous_enabled=previous, new_enabled=body.enabled, reason=body.reason))
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service=service, outcome="changed", reason="ENABLED" if body.enabled else "DISABLED")
    return setting_json(db, db.get(McpSetting, tenant_id))


@app.get("/api/v1/admin/tenants/{tenant_id}/access-changes", response_model=list[AccessChangeItem],
         tags=["Admin"], responses=ERRORS)
def admin_access_changes(tenant_id: str, limit: int = Query(25, ge=1, le=200),
                         db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    tenant_or_404(db, tenant_id)
    return db.scalars(select(AccessChange).where(AccessChange.tenant_id == tenant_id).order_by(AccessChange.id.desc()).limit(limit)).all()


def audit_json(event: AuditEvent):
    return {"id": event.id, "request_id": event.request_id, "actor": event.actor,
            "tenant_id": event.tenant_id, "employee_id": event.employee_id, "service": event.service,
            "outcome": event.outcome, "reason": event.reason, "created_at": event.created_at}


@app.get("/api/v1/admin/audit-events", tags=["Admin"], responses=ERRORS)
def admin_audit(tenantId: str | None = None, outcome: str | None = None, limit: int = Query(default=50, ge=1, le=200),
                db: Session = Depends(get_db), _claims: dict = Depends(require_admin())):
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if tenantId:
        tenant_or_404(db, tenantId)
        query = query.where(AuditEvent.tenant_id == tenantId)
    if outcome:
        query = query.where(AuditEvent.outcome == outcome)
    return [audit_json(event) for event in db.scalars(query)]
