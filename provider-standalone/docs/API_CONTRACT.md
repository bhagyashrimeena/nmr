# NMR Provider API Contract — Integration Handoff

**Version:** 1.0 · **Base URL (same machine):** `http://127.0.0.1:8000` · **Format:** JSON over HTTP · **Data:** wholly synthetic.

This contract is for the teammate implementing an **MCP adapter / Toyota employee assistant**. It is not an official bank API and does not expose real Nomura systems or real employee information.

## Authorization model

1. Each request to an external client route must have `Authorization: Bearer <signed JWT>`.
2. JWT validation checks HS256 signature, `iss=nmr-workplace-demo`, `aud=nmr-provider-api`, `iat`, `nbf`, `exp`, subject, role and scopes. This is a demo-only scheme.
3. Employee principal must have `role=employee`, `scope=workplace:read`, a server-verified `tenant_id`, and a server-verified `employee_id`.
4. Backend verifies tenant master access, per-tenant/per-service access, and employee membership/status on **each protected call**.
5. The integration must not supply or trust a tenant or employee ID from the natural-language user message to override authenticated identity. Service routes use `/me`.
6. Never send NMR admin JWTs to an external employee MCP client.

For local testing, request synthetic identity credentials:

```http
POST /api/v1/demo/session
Content-Type: application/json

{"persona":"toyota-001"}
```

Demo personas: `admin`, `toyota-001`, `toyota-002`, `toyota-003`, `harbor-001`.

Local token issuance **must not be enabled in shared environments**. For a proper cross-machine POC, agree on signed delegated identity/issuer and audience, move credential generation to the trusted test identity component, and perform security review.

## Proposed MCP tool mapping (tools not implemented by NMR)

| MCP tool suggestion | NMR provider REST endpoint | Permission key | Employee scope |
|---|---|---|---|
| `get_stock_ownership_summary` | `GET /api/v1/client/me/stock-ownership` | `stock-ownership` | current employee only |
| `get_pension_summary` | `GET /api/v1/client/me/pension` | `pension` | current employee only |
| `search_financial_wellness` | `GET /api/v1/client/wellness/resources?topic=Retirement` | `wellness` | educational catalog + progress |
| `calculate_savings_scenario` | `GET /api/v1/client/wellness/savings-projection?monthly_jpy=15000&years=10&annual_return_pct=0` | `wellness` | non-advisory deterministic calculator |
| `get_custody_summary` | `GET /api/v1/client/me/custody` | `custody` | current employee only |
| `get_equity_awards` | `GET /api/v1/client/me/equity-compensation` | `equity-compensation` | current employee only |

Tool names are **proposals for this POC**, not current vendor MCP contracts. Financial read operations return normalized domain JSON; avoid doing financial arithmetic inside the MCP adapter.

## External response examples

### Stock ownership

`GET /api/v1/client/me/stock-ownership`

```json
{
  "service": "stock-ownership",
  "employee_id": "TYO-001",
  "enrolled": true,
  "currency": "JPY",
  "summary": {
    "shares_held": 119,
    "employee_contributions_jpy": 340000,
    "employer_incentives_jpy": 17000,
    "total_purchases_jpy": 357000,
    "uninvested_cash_jpy": 0,
    "illustrative_market_value_jpy": 371280
  },
  "contributions": [],
  "purchases": []
}
```

The actual response includes full contribution and purchase ledgers. Fields omitted above are available from `/openapi.json` and the running API. The totals above are fixed test data and arithmetically consistent.

### Pension

`GET /api/v1/client/me/pension?years=20&annual_return_pct=4`

Includes account, yearly contributions, asset allocations and a 20-year purely illustrative future-value projection. Inputs: `years` 1–40; `annual_return_pct` 0–12. It is not investment advice or a guaranteed return.

### Financial wellness

`GET /api/v1/client/wellness/resources?topic=Retirement`

Returns educational resources (title, topic, summary, body, reading time, synthetic learning progress). Allowed topics include retirement, shareholding, budgeting, investing, custody and equity. The read-only educational savings projection uses `GET /api/v1/client/wellness/savings-projection` with `monthly_jpy` (0–1,000,000), `years` (1–40), and `annual_return_pct` (0–12). It is independently gated by the wellness service policy.

### Custody

`GET /api/v1/client/me/custody`

Returns custody positions, illustrative market values, dividends distinguished as `PAID` vs `ANNOUNCED`, corporate-action notifications, and historical synthetic settlements.

### Equity compensation

`GET /api/v1/client/me/equity-compensation`

Returns RSU and option grants, vested vs scheduled events, exercise price for options, and the next scheduled vesting date. **No exercise, award release, trade, transfer or settlement tools are exposed.**

If a synthetic employee is not enrolled in a service, the API returns a successful JSON record with `enrolled=false`, not invented balances.

## Authorization status and errors

| Condition | HTTP | Error code |
|---|---:|---|
| Missing, bad or expired JWT | 401 | `UNAUTHENTICATED` |
| Wrong role or missing `workplace:read` | 403 | `INSUFFICIENT_PERMISSIONS` |
| Tenant master disabled | 403 | `MCP_ACCESS_DISABLED` |
| That service disabled for tenant | 403 | `SERVICE_ACCESS_DISABLED` |
| Employee missing, inactive or belongs to different tenant | 403 | `RESOURCE_NOT_ACCESSIBLE` |
| Unknown admin resource | 404 | `NOT_FOUND` |
| Invalid parameter | 422 | FastAPI validation detail |

Structured denial:

```json
{"error":{"code":"SERVICE_ACCESS_DISABLED","message":"External access to Corporate Pension is disabled for this corporate client.","request_id":"<opaque-id>"}}
```

Successful and denied external requests are audited. All client responses include `Cache-Control: no-store, private` and an `X-Request-ID` correlation header.

## NMR admin endpoints (NMR internal use only)

| Verb | Endpoint |
|---|---|
| GET | `/api/v1/admin/tenants` |
| GET | `/api/v1/admin/tenants/{tenant_id}/overview` |
| GET | `/api/v1/admin/tenants/{tenant_id}/employees` |
| GET | `/api/v1/admin/tenants/{tenant_id}/employees/{employee_id}/services/{service_key}` |
| GET | `/api/v1/admin/tenants/{tenant_id}/mcp-access` |
| PATCH | `/api/v1/admin/tenants/{tenant_id}/mcp-access` |
| PATCH | `/api/v1/admin/tenants/{tenant_id}/service-access/{service_key}` |
| GET | `/api/v1/admin/audit-events?tenant_id=toyota-demo&outcome=DENIED` |
| GET | `/api/v1/catalog/services` (public catalog metadata) |

Master and service PATCH body:

```json
{"enabled":false,"reason":"External access disabled for authorization test"}
```

Only `role=admin` with `admin:write` may change access. Turning the master switch OFF takes precedence without modifying the five saved service states. NMR admin browsing remains operational.

## Python caller example (synthetic local demo only)

```python
import requests
base = "http://127.0.0.1:8000"
identity = requests.post(f"{base}/api/v1/demo/session", json={"persona":"toyota-001"}).json()
headers = {"Authorization": f"Bearer {identity['access_token']}"}
result = requests.get(f"{base}/api/v1/client/me/stock-ownership", headers=headers)
print(result.status_code, result.json())
```

## Cross-machine integration

`127.0.0.1` is only reachable from the same machine. A separately hosted MCP adapter cannot call this address. Do not expose the demo-token endpoint on an untrusted network. For a team demo across machines, coordinate a private development network, mutually agreed test authentication, restricted network rules, and an approved TLS/reverse proxy. Exact address and identity exchange are integration decisions for your team; they are not hardcoded into the API.
