# NMR provider REST contract for the MCP adapter

This is the provider-side contract for the fictional NMR workplace finance POC. The Toyota chatbot and MCP adapter are implemented by the other developer. The five suggested MCP tool names below are a proposed mapping, not implemented tools.

Base URL for local development: `http://127.0.0.1:8000`. All financial routes are versioned under `/api/v1`. Machine-readable OpenAPI is served at `/openapi.json`; Swagger UI is at `/docs`. A checked-in snapshot is at `docs/openapi.json`.

## Authentication and represented employee

Send `Authorization: Bearer <signed JWT>` on every external request. The adapter must receive a signed, short-lived token for the represented employee through an agreed local demo exchange. The NMR backend validates HS256 signature, issuer `nmr-demo`, audience `nmr-workplace-api`, `iat`, `nbf`, and `exp`.

Required claims for a client request:

```json
{
  "iss": "nmr-demo",
  "aud": "nmr-workplace-api",
  "sub": "employee:EMP-001",
  "role": "employee",
  "scopes": ["read:finance"],
  "tenant_id": "toyota-demo",
  "employee_id": "EMP-001",
  "iat": 1795600000,
  "nbf": 1795600000,
  "exp": 1795601800
}
```

The timestamps above illustrate claim shape only. Mint current tokens with `python -m app.tokens --tenant toyota-demo --employee EMP-001` from `backend/`, after setting `.env`. The secret stays on the NMR backend/local integration environment and never enters the browser bundle. The adapter must not construct employee identity from a chat prompt or arbitrary HTTP header. For this local POC, a trusted teammate can mint a token with the shared local secret; a production design would need delegated OAuth/token exchange and independent key management.

Every client request is checked in this order: valid token and role/scope; tenant policy (`mcp_enabled`); employee belongs to tenant and is active; employee is allowed to access the service. The administrator route uses a separate admin token. A tenant whose MCP access is disabled receives `403 MCP_ACCESS_DISABLED` on every new client call, even if tool discovery still lists the operation. Previously returned chat content cannot be revoked retroactively.

## External routes and proposed tool mapping

| Proposed tool | HTTP route | Response highlights |
|---|---|---|
| `get_stock_ownership_summary` | `GET /api/v1/client/me/stock-ownership` | Shares held, monthly and total payroll contributions, recent purchase lots |
| `get_pension_summary` | `GET /api/v1/client/me/pension` | Balance, employee/employer contributions, allocations |
| `find_financial_wellness_content` | `GET /api/v1/client/wellness/resources?topic=retirement` | Educational articles; optional `topic` filter |
| `get_custody_summary` | `GET /api/v1/client/me/custody` | Positions, credited dividends, corporate-action notices |
| `get_equity_compensation_summary` | `GET /api/v1/client/me/equity-compensation` | RSU/option grants, vested/unvested units, next scheduled vesting |

No client route accepts tenant or employee IDs in request arguments. All values are deterministic synthetic records, as of `2026-11-25`. No execution or financial transaction route exists.

Example stock response for `EMP-001` (purchase history abbreviated):

```json
{
  "tenant_id": "toyota-demo",
  "employee_id": "EMP-001",
  "as_of": "2026-11-25",
  "currency": "JPY",
  "plan_id": "TDEMO-SHARE-01",
  "shares_held": 120,
  "monthly_contribution_jpy": 20000,
  "total_contributions_jpy": 240000,
  "contributions": [{"month": "2026-11-01", "amount_jpy": 20000}],
  "recent_purchases": [{"purchase_date": "2026-11-01", "shares": 4, "price_jpy": 5000, "amount_jpy": 20000}]
}
```

## Admin routes

`POST /api/v1/auth/admin-token` accepts `{ "username": "nmr-admin", "password": "<NMR_ADMIN_PASSWORD>" }` and returns a one-hour admin JWT. This is for the local portal only.

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/admin/tenants` | List fictional tenants |
| GET | `/api/v1/admin/tenants/{tenant_id}/overview` | Tenant name, employee count, access and recent activity |
| GET | `/api/v1/admin/tenants/{tenant_id}/employees` | Employee list and service permissions |
| GET | `/api/v1/admin/tenants/{tenant_id}/employees/{employee_id}/service-summary` | Read-only five-service admin view |
| GET | `/api/v1/admin/tenants/{tenant_id}/mcp-access` | Current persisted policy and change metadata |
| PATCH | `/api/v1/admin/tenants/{tenant_id}/mcp-access` | Set policy; body `{ "enabled": false, "reason": "Demo access review" }` |
| GET | `/api/v1/admin/audit-events?tenantId=toyota-demo&outcome=denied` | Request events, newest first; optional filters and `limit` |
| GET | `/health` | Service status |

Only a JWT with role `admin` and scope `admin:write` may patch the access setting. Admin browsing does not impersonate an employee and is not gated by the tenant MCP setting.

## Errors and correlation

The backend returns a generated `X-Request-ID` response header, or echoes a supplied safe `X-Request-ID` value. Example:

```json
{"error":{"code":"MCP_ACCESS_DISABLED","message":"External access is disabled for this client.","request_id":"http-smoke-denied"}}
```

`401` means missing, invalid, or expired token. `403` means forbidden scope/service or disabled access. `404` means absent tenant, employee, or requested service record. `422` means invalid request shape. Protected responses include `Cache-Control: no-store`. Successful and policy-denied client calls record request ID, tenant, employee, service, outcome, reason, and timestamp. Tokens and passwords are never stored in audit events.

## Teammate handoff decisions

1. Agree on the adapter host/port and local token handoff. Do not place the signing secret in the Toyota browser.
2. Confirm final MCP tool names and response formatting. The NMR REST route names above are implemented and stable for this POC.
3. Demonstrate stock ON/OFF/ON first; the same backend policy applies to the other four client routes.
