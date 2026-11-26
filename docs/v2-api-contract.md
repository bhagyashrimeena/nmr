# V2 provider API contract

Base URL: `http://127.0.0.1:8000`. All routes below are implemented under `/api/v2`. The original `/api/v1` routes remain available. The complete machine-readable route listing is in `docs/openapi.json` and at `/openapi.json` when the server runs.

## Authentication and policy

Send `Authorization: Bearer <employee JWT>` on every client request. The token must contain issuer `nmr-demo`, audience `nmr-workplace-api`, subject `employee:<employee_id>`, role `employee`, `tenant_id`, `employee_id`, `iat`, `nbf`, `exp`, and scope `read:finance`. The service key is checked against employee eligibility, the tenant master switch, and the tenant service switch on every request. The adapter must derive tenant and employee only from the signed token. No client route accepts an arbitrary tenant or employee ID.

For a local integration, mint a 30-minute read token from `backend/` with:

```powershell
$token = .\.venv\Scripts\python.exe -m app.tokens --tenant toyota-demo --employee EMP-001
Invoke-RestMethod 'http://127.0.0.1:8000/api/v2/client/me/shareholding/summary' -Headers @{ Authorization = "Bearer $token" }
```

Draft routes require a service-specific scope in addition to the employee identity and access policy: `draft:stock`, `draft:pension`, or `draft:equity`. Use `python -m app.tokens --tenant toyota-demo --employee EMP-001 --draft stock` for a local stock draft token. Include a unique `Idempotency-Key` header of 8-80 characters. Draft operations create local requests; they do not execute transactions.

The provider administrator uses `POST /api/v1/auth/admin-token` with username `nmr-admin` and the locally configured password. Admin routes require `admin:read` or `admin:write` and are not gated by external MCP access. Keep the shared JWT signing key on the backend and integration host, never in a browser bundle.

## Client routes

| Service | Routes | Primary content |
|---|---|---|
| Stock ownership | `GET /client/me/shareholding/{summary,contributions,purchases,dividends,ledger}`; `GET /client/me/shareholding/transfers/{request_id}`; `POST /client/me/shareholding/transfer-drafts` | Plan balance, posted payroll cash, settled purchases, share events, transfer state |
| Pension | `GET /client/me/pension/{account,positions,contributions,funds,allocation,projections}`; `GET /client/me/pension/instructions/{instruction_id}`; `POST /client/me/pension/allocation-drafts` | Account and fund units, NAV, future contribution allocation |
| Equity | `GET /client/me/equity/{grants,vesting,options,releases,statement}`; `GET /client/me/equity/grants/{grant_id}`; `POST /client/me/equity/exercise-drafts` | Issued awards, tranches, exercise eligibility, release history |
| Custody | `GET /client/me/custody/{positions,history,dividends,actions,transfers,settlements,statement}` | Separate custody inventory, cash events, entitlements, transfer status |
| Wellness | `GET /client/wellness/{education,progress,seminars}`; `GET /client/wellness/benefits/{benefit_key}`; `GET /client/wellness/calculators/monthly-savings` | Published education, source-backed tenant rules, learning records, calculator |

Prefix each listed route with `/api/v2`. If the master switch is off, new external calls return `403 MCP_ACCESS_DISABLED`. If a service switch is off, its routes return `403 SERVICE_ACCESS_DISABLED`, including draft and calculator routes. An active employee must also be allowed to use the service. Protected responses use `Cache-Control: no-store` and carry an `X-Request-ID` header.

The read responses have a fixed `as_of` date of `2026-11-26` for operational records. JPY amounts and quantities are decimal strings in V2 financial event views. A released award is separate from a custody delivery confirmation. A pension allocation instruction changes future contributions only, not existing fund holdings. An announced dividend does not increase cash. An association transfer decreases stock units and credits custody units under the same correlation ID only after completion.

### Examples

```http
GET /api/v2/client/me/shareholding/summary
Authorization: Bearer <employee-token>
```

A successful `EMP-001` response includes `shares_held: "120.000000"` and `uninvested_cash_jpy: "12000.00"`. `EMP-002` has a rejected November payroll line with no cash or share effect. The linked stock and custody views should be read independently; their opening holdings represent separate inventories.

```http
GET /api/v2/client/wellness/benefits/shareholding_incentive
Authorization: Bearer <employee-token>
```

Toyota receives the exact `TOYOTA-SHARE-01/RULES/2026` source reference and effective date. Sakura receives `404 BENEFIT_RULE_NOT_AVAILABLE` because that rule is absent for its tenant. Do not invent a benefit rule in the adapter.

```http
GET /api/v2/client/wellness/calculators/monthly-savings?monthly_jpy=10000&months=12&annual_rate_percent=0
Authorization: Bearer <employee-token>
```

The result includes formula ID `MONTHLY_END_OF_PERIOD_COMPOUND_V1`, inputs, monthly rate, total contributions `120000.00`, future value `120000.00`, and disclosure. The caller should show the assumptions alongside the result.

## Administrator workflow routes

All routes below begin `/api/v2/admin/tenants/{tenant_id}`. Admin users can also use `/api/v1/admin/tenants/{tenant_id}/mcp-access` and `/service-access/{service}` for the master and five service switches.

| Service | Read | Review or create |
|---|---|---|
| Stock | `GET /shareholding/operations` | `POST /shareholding/payroll-batches`; `PATCH /shareholding/payroll-batches/{batch_id}`; `POST /shareholding/purchase-cycles`; `PATCH /shareholding/purchase-cycles/{cycle_id}`; `PATCH /shareholding/transfers/{request_id}` |
| Pension | `GET /pension/operations` | `PATCH /pension/instructions/{instruction_id}` |
| Equity | `GET /equity/operations` | `PATCH /equity/grants/{grant_id}`; `PATCH /equity/releases/{release_id}` |
| Custody | `GET /custody/operations` | `PATCH /custody/actions/{action_id}`; `PATCH /custody/dividends/{dividend_id}` |
| Wellness | `GET /wellness/operations` | `PATCH /wellness/content/{content_id}` |

State transitions require a nonempty review reason. Invalid transitions return `409 STATE_CONFLICT`. An operator may view all tenant records through admin routes, but cannot access a record from another tenant through its ID. The client APIs always select the signed employee's own record.

## Errors and audit

Errors use `{ "error": { "code": "...", "message": "...", "request_id": "..." } }`. Common codes are `UNAUTHENTICATED` (401), `INSUFFICIENT_PERMISSIONS` (403), `RESOURCE_NOT_ACCESSIBLE` (403), `MCP_ACCESS_DISABLED` (403), `SERVICE_ACCESS_DISABLED` (403), `RESOURCE_NOT_FOUND` (404), `BENEFIT_RULE_NOT_AVAILABLE` (404), `DUPLICATE_REQUEST` (409), `STATE_CONFLICT` (409), and `INVALID_REQUEST` (422). Domain validation may also return `RECONCILIATION_FAILED`, `UNITS_UNAVAILABLE`, or `INVALID_PLAN_RULE`. V2 protected calls write request ID, actor, scopes, service, operation, outcome, reason, tenant, and employee to the operation audit table. Token strings and passwords are never written there.

## Integration boundary

One MCP server can expose tools across all five categories and call these REST routes. The chatbot and MCP server remain owned by the separate integration developer. The NMR application contains no order, sale, option exercise, payment execution, or external custody settlement connection. The local records are fixed test data and should not be connected to real financial accounts. A deployed integration needs a managed employee token exchange and stronger identity infrastructure. End-to-end request-to-chatbot verification remains outstanding until that integration is available.
