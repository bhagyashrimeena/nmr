"""Local-only demo authentication. Never use these demo personas in production."""
import os
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from fastapi import Header
import jwt

JWT_SECRET = os.getenv("NMR_JWT_SECRET", "local-demo-secret-change-before-sharing")
ISSUER = "nmr-workplace-demo"
AUDIENCE = "nmr-provider-api"
DEMO_MODE = os.getenv("NMR_DEMO_MODE", "true").lower() == "true"

@dataclass(frozen=True)
class Principal:
    sub: str
    role: str
    tenant_id: str | None
    employee_id: str | None
    scopes: frozenset[str]

DEMO_PERSONAS = {
    "admin": {"sub": "nmr-admin-01", "role": "admin", "tenant_id": None, "employee_id": None, "scopes": ["admin:read", "admin:write"]},
    "toyota-001": {"sub": "toyota-employee-001", "role": "employee", "tenant_id": "toyota-demo", "employee_id": "TYO-001", "scopes": ["workplace:read"]},
    "toyota-002": {"sub": "toyota-employee-002", "role": "employee", "tenant_id": "toyota-demo", "employee_id": "TYO-002", "scopes": ["workplace:read"]},
    "toyota-003": {"sub": "toyota-employee-003", "role": "employee", "tenant_id": "toyota-demo", "employee_id": "TYO-003", "scopes": ["workplace:read"]},
    "harbor-001": {"sub": "harbor-employee-001", "role": "employee", "tenant_id": "harbor-demo", "employee_id": "HBR-001", "scopes": ["workplace:read"]},
}

def issue_demo_token(persona: str) -> str:
    claims = DEMO_PERSONAS[persona].copy()
    ts = datetime.now(timezone.utc)
    claims.update({"iss": ISSUER, "aud": AUDIENCE, "iat": ts, "nbf": ts, "exp": ts+timedelta(hours=2)})
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")

def decode_token(raw: str) -> Principal:
    claims = jwt.decode(raw, JWT_SECRET, algorithms=["HS256"], issuer=ISSUER, audience=AUDIENCE, options={"require": ["sub","iss","aud","exp","iat","nbf","role"]})
    return Principal(sub=claims["sub"], role=claims["role"], tenant_id=claims.get("tenant_id"), employee_id=claims.get("employee_id"), scopes=frozenset(claims.get("scopes", [])))
