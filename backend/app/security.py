import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import SERVICES
from .db import get_db
from .models import AuditEvent, Employee, McpSetting, Tenant, TenantServiceSetting
from .v2_models import OperationAudit, TenantOperationalStatus

ISSUER = "nmr-demo"
AUDIENCE = "nmr-workplace-api"
bearer = HTTPBearer(auto_error=False)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def secret():
    value = os.getenv("NMR_JWT_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("Set NMR_JWT_SECRET to at least 32 characters (see backend/.env.example)")
    return value


def mint_token(*, sub: str, role: str, scopes: list[str], tenant_id: str | None = None, employee_id: str | None = None, minutes: int = 30):
    now = datetime.now(timezone.utc)
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": sub, "role": role, "scopes": scopes,
              "iat": now, "nbf": now, "exp": now + timedelta(minutes=minutes)}
    if tenant_id:
        claims["tenant_id"] = tenant_id
    if employee_id:
        claims["employee_id"] = employee_id
    return jwt.encode(claims, secret(), algorithm="HS256")


def read_claims(credentials: HTTPAuthorizationCredentials | None):
    if not credentials:
        raise ApiError(401, "UNAUTHENTICATED", "A bearer token is required.")
    try:
        claims = jwt.decode(credentials.credentials, secret(), algorithms=["HS256"], issuer=ISSUER, audience=AUDIENCE,
                            options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub"]})
    except jwt.PyJWTError:
        raise ApiError(401, "UNAUTHENTICATED", "The bearer token is invalid or expired.") from None
    return claims


def audit(db: Session, request: Request, *, actor: str, tenant_id: str | None, employee_id: str | None, service: str, outcome: str, reason: str):
    db.add(AuditEvent(request_id=request.state.request_id, actor=actor, tenant_id=tenant_id,
                      employee_id=employee_id, service=service, outcome=outcome, reason=reason))
    if request.url.path.startswith("/api/v2/"):
        db.add(OperationAudit(request_id=request.state.request_id, actor=actor, tenant_id=tenant_id,
                              employee_id=employee_id, principal_scopes=getattr(request.state, "principal_scopes", ""),
                              service=service, operation=getattr(request.state, "operation", request.method.lower()),
                              outcome=outcome, reason=reason))
    db.commit()


def require_admin(write: bool = False):
    def dependency(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        claims = read_claims(credentials)
        scope = "admin:write" if write else "admin:read"
        if claims.get("role") != "admin" or scope not in (claims.get("scopes") or []):
            raise ApiError(403, "INSUFFICIENT_PERMISSIONS", "Administrator permission is required.")
        return claims
    return dependency


def require_provider(service: str, write: bool = False):
    """Provider administrators and tenant-scoped service operators only."""
    if service not in SERVICES:
        raise ValueError(f"Unknown provider service: {service}")

    def dependency(tenant_id: str, request: Request, db: Session = Depends(get_db),
                   credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        claims = read_claims(credentials)
        request.state.principal_scopes = ",".join(claims.get("scopes") or [])
        scopes = claims.get("scopes") or []
        if claims.get("role") == "admin" and ("admin:write" if write else "admin:read") in scopes:
            return claims
        needed = f"ops:{service}:{'write' if write else 'read'}"
        if (claims.get("role") == "operator" and claims.get("tenant_id") == tenant_id
                and claims.get("sub", "").startswith("operator:") and needed in scopes):
            return claims
        audit(db, request, actor=claims.get("sub", "unknown"), tenant_id=tenant_id,
              employee_id=None, service=service, outcome="denied", reason="INSUFFICIENT_PERMISSIONS")
        raise ApiError(403, "INSUFFICIENT_PERMISSIONS", "Provider service permission is required.")

    return dependency


def require_corporate():
    def dependency(tenant_id: str, request: Request, db: Session = Depends(get_db),
                   credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        claims = read_claims(credentials)
        request.state.principal_scopes = ",".join(claims.get("scopes") or [])
        if (claims.get("role") != "corporate_admin" or claims.get("tenant_id") != tenant_id
                or not claims.get("sub", "").startswith("corporate:")
                or "plan:read" not in (claims.get("scopes") or [])):
            audit(db, request, actor=claims.get("sub", "unknown"), tenant_id=tenant_id,
                  employee_id=None, service="corporate_reporting", outcome="denied",
                  reason="INSUFFICIENT_PERMISSIONS")
            raise ApiError(403, "INSUFFICIENT_PERMISSIONS", "Corporate plan permission is required.")
        return claims

    return dependency


def require_client(service: str, operation: str = "read"):
    if service not in SERVICES:
        raise ValueError(f"Unknown client service: {service}")
    if operation not in {"read", "draft"}:
        raise ValueError(f"Unknown client operation: {operation}")

    def dependency(request: Request, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        request.state.operation = operation
        try:
            claims = read_claims(credentials)
        except ApiError as exc:
            audit(db, request, actor="anonymous", tenant_id=None, employee_id=None,
                  service=service, outcome="denied", reason=exc.code)
            raise
        tenant_id = claims.get("tenant_id")
        employee_id = claims.get("employee_id")
        actor = claims.get("sub", "unknown")
        request.state.principal_scopes = ",".join(claims.get("scopes") or [])

        def deny(code: str, message: str, status: int = 403):
            audit(db, request, actor=actor, tenant_id=tenant_id, employee_id=employee_id,
                  service=service, outcome="denied", reason=code)
            raise ApiError(status, code, message)

        required = "read:finance" if operation == "read" else f"draft:{service}"
        if claims.get("role") != "employee" or required not in (claims.get("scopes") or []):
            deny("INSUFFICIENT_PERMISSIONS", "Employee permission for this operation is required.")
        if not isinstance(tenant_id, str) or not isinstance(employee_id, str) or actor != f"employee:{employee_id}":
            deny("RESOURCE_NOT_ACCESSIBLE", "Employee identity claims are inconsistent.")
        if not db.get(Tenant, tenant_id):
            deny("RESOURCE_NOT_ACCESSIBLE", "Tenant is not available.")
        tenant_status = db.get(TenantOperationalStatus, tenant_id)
        if not tenant_status or tenant_status.status != "ACTIVE":
            deny("TENANT_INACTIVE", "The corporate client is not active.")
        setting = db.get(McpSetting, tenant_id)
        if not setting or not setting.enabled:
            deny("MCP_ACCESS_DISABLED", "External access is disabled for this client.")
        service_setting = db.scalar(select(TenantServiceSetting).where(
            TenantServiceSetting.tenant_id == tenant_id, TenantServiceSetting.service == service))
        if not service_setting or not service_setting.enabled:
            deny("SERVICE_ACCESS_DISABLED", f"External access to {SERVICES[service]['title']} is disabled for this client.")
        employee = db.get(Employee, employee_id)
        if not employee or employee.tenant_id != tenant_id or not employee.active:
            deny("RESOURCE_NOT_ACCESSIBLE", "Employee record is not available.")
        if service not in employee.allowed_services.split(","):
            deny("INSUFFICIENT_PERMISSIONS", "This employee cannot access the service.")
        return claims
    return dependency


def verify_admin_password(username: str, password: str):
    expected = os.getenv("NMR_ADMIN_PASSWORD", "")
    return bool(expected) and hmac.compare_digest(username, "nmr-admin") and hmac.compare_digest(password, expected)
