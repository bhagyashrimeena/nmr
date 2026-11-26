"""NMR Workplace Finance POC. Fictional tenants, deterministic services, no execution."""
from __future__ import annotations
import os, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI, Depends, Header, HTTPException, Request, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import jwt
from .database import get_db
from .models import Tenant, Employee, ServicePermission, AuditEvent
from .security import DEMO_MODE, DEMO_PERSONAS, issue_demo_token, decode_token, Principal
from .seed import seed_database, SERVICES
from .domain import get_service, savings_projection

seed_database()
app = FastAPI(title="NMR Workplace Finance Provider API — Synthetic Demo", version="1.0.0", description="Read-only mock workplace finance services with tenant-scoped, service-level MCP access policy. Not connected to any real financial institution.")
origins = [x.strip() for x in os.getenv("NMR_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET","PATCH","POST","OPTIONS"],allow_headers=["Authorization","Content-Type","X-Request-ID"], expose_headers=["X-Request-ID"])

class ApiError(Exception):
    def __init__(self,status:int,code:str,message:str):
        self.status,self.code,self.message=status,code,message

@app.middleware("http")
async def add_request_id(request:Request,call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    if request.url.path.startswith("/api/v1/client/"):
        response.headers["Cache-Control"]="no-store, private"
    return response

@app.exception_handler(ApiError)
async def api_error(request:Request,exc:ApiError):
    return JSONResponse(status_code=exc.status,content={"error":{"code":exc.code,"message":exc.message,"request_id":getattr(request.state,"request_id","unknown")}},headers={"Cache-Control":"no-store"})

class DemoPersona(BaseModel):
    persona: str

class EnabledPatch(BaseModel):
    enabled: bool
    reason: str = Field(min_length=4,max_length=240)


def principal(authorization:Annotated[str|None,Header(alias="Authorization")]=None) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401,"UNAUTHENTICATED","A valid Bearer access token is required.")
    try:
        return decode_token(authorization[7:])
    except (jwt.InvalidTokenError,ValueError,KeyError):
        raise ApiError(401,"UNAUTHENTICATED","Access token is invalid or expired.")


def require_admin(p:Principal):
    if p.role!="admin" or "admin:read" not in p.scopes:
        raise ApiError(403,"INSUFFICIENT_PERMISSIONS","NMR administrator access required.")


def require_admin_write(p:Principal):
    require_admin(p)
    if "admin:write" not in p.scopes:
        raise ApiError(403,"INSUFFICIENT_PERMISSIONS","NMR administrator write permission required.")


def tenant_or_404(db:Session,tenant_id:str) -> Tenant:
    row=db.get(Tenant,tenant_id)
    if row is None:
        raise ApiError(404,"NOT_FOUND","Corporate client not found.")
    return row


def permission_or_404(db:Session,tenant_id:str,service_key:str):
    if service_key not in SERVICES:
        raise ApiError(404,"NOT_FOUND","Workplace-finance service not found.")
    row=db.scalar(select(ServicePermission).where(ServicePermission.tenant_id==tenant_id,ServicePermission.service_key==service_key))
    if not row:
        raise ApiError(404,"NOT_FOUND","Service setting not found.")
    return row


def audit(db:Session,request:Request,actor:str,tenant_id:str|None,employee_id:str|None,action:str,service_key:str|None,outcome:str,reason:str):
    db.add(AuditEvent(request_id=request.state.request_id,actor=actor,tenant_id=tenant_id,employee_id=employee_id,action=action,service_key=service_key,outcome=outcome,reason=reason[:240]))
    db.commit()


def external_data(service_key:str,request:Request,db:Session,p:Principal,**kwargs):
    if p.role!="employee" or "workplace:read" not in p.scopes or not p.tenant_id or not p.employee_id:
        audit(db,request,p.sub,p.tenant_id,p.employee_id,"EXTERNAL_READ",service_key,"DENIED","INSUFFICIENT_PERMISSIONS")
        raise ApiError(403,"INSUFFICIENT_PERMISSIONS","Your principal does not have financial-service read access.")
    tenant=db.get(Tenant,p.tenant_id)
    if not tenant or not tenant.mcp_enabled:
        audit(db,request,p.sub,p.tenant_id,p.employee_id,"EXTERNAL_READ",service_key,"DENIED","MCP_ACCESS_DISABLED")
        raise ApiError(403,"MCP_ACCESS_DISABLED","External MCP access is disabled for this corporate client.")
    access=db.scalar(select(ServicePermission).where(ServicePermission.tenant_id==p.tenant_id,ServicePermission.service_key==service_key))
    if not access or not access.enabled:
        audit(db,request,p.sub,p.tenant_id,p.employee_id,"EXTERNAL_READ",service_key,"DENIED","SERVICE_ACCESS_DISABLED")
        raise ApiError(403,"SERVICE_ACCESS_DISABLED",f"External access to {SERVICES[service_key]['title']} is disabled for this corporate client.")
    employee=db.get(Employee,p.employee_id)
    if not employee or employee.tenant_id!=p.tenant_id or employee.status!="ACTIVE":
        audit(db,request,p.sub,p.tenant_id,p.employee_id,"EXTERNAL_READ",service_key,"DENIED","RESOURCE_NOT_ACCESSIBLE")
        raise ApiError(403,"RESOURCE_NOT_ACCESSIBLE","Employee records cannot be accessed by this principal.")
    result=get_service(db,service_key,p.employee_id,**kwargs)
    audit(db,request,p.sub,p.tenant_id,p.employee_id,"EXTERNAL_READ",service_key,"ALLOWED","ACCESS_GRANTED")
    return result

@app.get("/health",tags=["system"])
def health():
    return {"status":"ok","mode":"fictional-demo","service_count":len(SERVICES)}

@app.get("/api/v1/catalog/services",tags=["system"])
def service_catalog():
    return [{"key":key,**meta} for key,meta in SERVICES.items()]

@app.post("/api/v1/demo/session",tags=["local-demo"])
def local_demo_session(body:DemoPersona):
    if not DEMO_MODE:
        raise ApiError(404,"NOT_FOUND","Demo sessions are disabled.")
    if body.persona not in DEMO_PERSONAS:
        raise ApiError(404,"NOT_FOUND","Unknown synthetic demo persona.")
    return {"access_token":issue_demo_token(body.persona),"token_type":"bearer","expires_in":7200,"persona":body.persona,"note":"Local demonstration credentials only; do not expose this endpoint in production."}

# External client endpoints: all check master and per-service policy on every invocation.
@app.get("/api/v1/client/me/stock-ownership",tags=["client: stock"])
def client_stock(request:Request,db:Session=Depends(get_db),p:Principal=Depends(principal)):
    return external_data("stock-ownership",request,db,p)

@app.get("/api/v1/client/me/pension",tags=["client: pension"])
def client_pension(request:Request,annual_return_pct:float=Query(4,ge=0,le=12),years:int=Query(20,ge=1,le=40),db:Session=Depends(get_db),p:Principal=Depends(principal)):
    return external_data("pension",request,db,p,annual_return_pct=annual_return_pct,years=years)

@app.get("/api/v1/client/wellness/resources",tags=["client: wellness"])
def client_wellness(request:Request,topic:str|None=Query(None,max_length=60),db:Session=Depends(get_db),p:Principal=Depends(principal)):
    return external_data("wellness",request,db,p,topic=topic)

@app.get("/api/v1/client/wellness/savings-projection",tags=["client: wellness"])
def client_savings_projection(request:Request,monthly_jpy:int=Query(15000,ge=0,le=1_000_000),years:int=Query(10,ge=1,le=40),annual_return_pct:float=Query(0,ge=0,le=12),db:Session=Depends(get_db),p:Principal=Depends(principal)):
    # Policy check and audit performed on every invocation, including calculations.
    external_data("wellness",request,db,p)
    return savings_projection(monthly_jpy,years,annual_return_pct)

@app.get("/api/v1/client/me/custody",tags=["client: custody"])
def client_custody(request:Request,db:Session=Depends(get_db),p:Principal=Depends(principal)):
    return external_data("custody",request,db,p)

@app.get("/api/v1/client/me/equity-compensation",tags=["client: equity"])
def client_equity(request:Request,db:Session=Depends(get_db),p:Principal=Depends(principal)):
    return external_data("equity-compensation",request,db,p)

# Admin remains available regardless of external MCP settings.
@app.get("/api/v1/admin/tenants",tags=["NMR admin"])
def admin_tenants(db:Session=Depends(get_db),p:Principal=Depends(principal)):
    require_admin(p)
    return [{"id":t.id,"name":t.name,"fictional":t.fictional,"mcp_enabled":t.mcp_enabled,"employee_count":db.scalar(select(func.count(Employee.id)).where(Employee.tenant_id==t.id))} for t in db.scalars(select(Tenant).order_by(Tenant.id)).all()]

@app.get("/api/v1/admin/tenants/{tenant_id}/overview",tags=["NMR admin"])
def admin_overview(tenant_id:str,db:Session=Depends(get_db),p:Principal=Depends(principal)):
    require_admin(p)
    t=tenant_or_404(db,tenant_id)
    employees=db.scalars(select(Employee).where(Employee.tenant_id==tenant_id)).all()
    service_permissions=db.scalars(select(ServicePermission).where(ServicePermission.tenant_id==tenant_id)).all()
    audit_rows=db.scalars(select(AuditEvent).where(AuditEvent.tenant_id==tenant_id).order_by(AuditEvent.id.desc()).limit(8)).all()
    return {"tenant":{"id":t.id,"name":t.name,"mcp_enabled":t.mcp_enabled},"employee_count":len(employees),"active_employee_count":sum(e.status=="ACTIVE" for e in employees),"total_services":len(SERVICES),"enabled_services":sum(x.enabled for x in service_permissions) if t.mcp_enabled else 0,"configured_enabled_services":sum(x.enabled for x in service_permissions),"recent_audit":[serialize_audit(a) for a in audit_rows]}

@app.get("/api/v1/admin/tenants/{tenant_id}/employees",tags=["NMR admin"])
def admin_employees(tenant_id:str,db:Session=Depends(get_db),p:Principal=Depends(principal)):
    require_admin(p)
    tenant_or_404(db,tenant_id)
    return [{"id":e.id,"tenant_id":e.tenant_id,"display_name":e.display_name,"department":e.department,"job_title":e.job_title,"joined_on":e.joined_on,"status":e.status} for e in db.scalars(select(Employee).where(Employee.tenant_id==tenant_id).order_by(Employee.id))]

@app.get("/api/v1/admin/tenants/{tenant_id}/employees/{employee_id}/services/{service_key}",tags=["NMR admin"])
def admin_employee_service(tenant_id:str,employee_id:str,service_key:str,topic:str|None=Query(None,max_length=60),annual_return_pct:float=Query(4,ge=0,le=12),years:int=Query(20,ge=1,le=40),db:Session=Depends(get_db),p:Principal=Depends(principal)):
    require_admin(p)
    tenant_or_404(db,tenant_id)
    if service_key not in SERVICES:
        raise ApiError(404,"NOT_FOUND","Service not found.")
    emp=db.get(Employee,employee_id)
    if not emp or emp.tenant_id!=tenant_id:
        raise ApiError(404,"NOT_FOUND","Employee not found for this tenant.")
    return get_service(db,service_key,employee_id,topic=topic,annual_return_pct=annual_return_pct,years=years)

@app.get("/api/v1/admin/tenants/{tenant_id}/employees/{employee_id}/wellness/savings-projection",tags=["NMR admin"])
def admin_savings_projection(tenant_id:str,employee_id:str,monthly_jpy:int=Query(15000,ge=0,le=1_000_000),years:int=Query(10,ge=1,le=40),annual_return_pct:float=Query(0,ge=0,le=12),db:Session=Depends(get_db),p:Principal=Depends(principal)):
    require_admin(p)
    employee=db.get(Employee,employee_id)
    if not employee or employee.tenant_id!=tenant_id:
        raise ApiError(404,"NOT_FOUND","Employee not found for this tenant.")
    return savings_projection(monthly_jpy,years,annual_return_pct)

@app.get("/api/v1/admin/tenants/{tenant_id}/mcp-access",tags=["NMR admin"])
def admin_access(tenant_id:str,db:Session=Depends(get_db),p:Principal=Depends(principal)):
    require_admin(p)
    t=tenant_or_404(db,tenant_id)
    permissions={s.service_key:s for s in db.scalars(select(ServicePermission).where(ServicePermission.tenant_id==tenant_id))}
    return {"tenant_id":tenant_id,"tenant_name":t.name,"master_enabled":t.mcp_enabled,"updated_at":t.updated_at.isoformat(),"updated_by":t.updated_by,"services":[{"key":key,**meta,"enabled":permissions[key].enabled if key in permissions else False,"effective_enabled":bool(t.mcp_enabled and permissions.get(key) and permissions[key].enabled),"updated_at":permissions[key].updated_at.isoformat() if key in permissions else None,"updated_by":permissions[key].updated_by if key in permissions else None} for key,meta in SERVICES.items()]}

@app.patch("/api/v1/admin/tenants/{tenant_id}/mcp-access",tags=["NMR admin"])
def admin_set_master(tenant_id:str,body:EnabledPatch,request:Request,db:Session=Depends(get_db),p:Principal=Depends(principal)):
    require_admin_write(p)
    t=tenant_or_404(db,tenant_id)
    old=t.mcp_enabled
    t.mcp_enabled=body.enabled
    t.updated_at=datetime.now(timezone.utc)
    t.updated_by=p.sub
    db.flush()
    audit(db,request,p.sub,tenant_id,None,"MASTER_ACCESS_CHANGED",None,"CHANGED",f"{old} -> {body.enabled}; reason: {body.reason}")
    return admin_access(tenant_id,db,p)

@app.patch("/api/v1/admin/tenants/{tenant_id}/service-access/{service_key}",tags=["NMR admin"])
def admin_set_service(tenant_id:str,service_key:str,body:EnabledPatch,request:Request,db:Session=Depends(get_db),p:Principal=Depends(principal)):
    require_admin_write(p)
    tenant_or_404(db,tenant_id)
    access=permission_or_404(db,tenant_id,service_key)
    old=access.enabled
    access.enabled=body.enabled
    access.updated_at=datetime.now(timezone.utc)
    access.updated_by=p.sub
    db.flush()
    audit(db,request,p.sub,tenant_id,None,"SERVICE_ACCESS_CHANGED",service_key,"CHANGED",f"{old} -> {body.enabled}; reason: {body.reason}")
    return admin_access(tenant_id,db,p)

def serialize_audit(row:AuditEvent):
    return {"id":row.id,"timestamp":row.created_at.isoformat(),"request_id":row.request_id,"actor":row.actor,"tenant_id":row.tenant_id,"employee_id":row.employee_id,"action":row.action,"service_key":row.service_key,"outcome":row.outcome,"reason":row.reason}

@app.get("/api/v1/admin/audit-events",tags=["NMR admin"])
def admin_audit_events(tenant_id:str|None=None,outcome:str|None=None,limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db),p:Principal=Depends(principal)):
    require_admin(p)
    stmt=select(AuditEvent)
    if tenant_id: stmt=stmt.where(AuditEvent.tenant_id==tenant_id)
    if outcome and outcome!="all": stmt=stmt.where(AuditEvent.outcome==outcome.upper())
    return [serialize_audit(row) for row in db.scalars(stmt.order_by(AuditEvent.id.desc()).limit(limit)).all()]

STATIC_DIR=Path(__file__).resolve().parent.parent/"static"
app.mount("/static",StaticFiles(directory=STATIC_DIR),name="static")
@app.get("/",include_in_schema=False)
def frontend():
    return FileResponse(STATIC_DIR/"index.html")
