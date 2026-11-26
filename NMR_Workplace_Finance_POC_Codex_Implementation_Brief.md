# NMR Workplace Finance POC — Codex Implementation Brief

**Status:** Proposed demo implementation. **Owner:** NMR/provider-side application. **Audience:** Codex coding agent and collaborating Toyota/MCP developer. **Context:** Team discussion dated 25 November 2026; first internal review discussed for Monday, 30 November 2026. **Data:** 100% synthetic.

## 1. Decisions made in the team meeting (source of truth)

- The research and POC topic is **Workplace Finance MCP**, inspired by the Morgan Stanley at Work announcement. It is **not** the previously explored Nomura/Goldman Sachs FX RFQ prototype.
- Use **NMR**, an explicitly fictional financial-services provider, rather than an internal bank's actual name or branding. Use **Toyota** only as a **hypothetical corporate client / tenant** for the demo. Do not imply a real commercial relationship.
- Build **two user-facing applications** across the team: (A) NMR workplace-finance provider/admin portal and backend; (B) Toyota employee chatbot. A teammate is implementing the Toyota chatbot and MCP integration. **This brief covers A only.**
- The NMR platform has **five workplace-finance service tabs:** (1) Employee Stock Ownership, (2) Corporate Pension Services, (3) Financial Wellness Programs, (4) Trust & Custody Services, (5) Equity Compensation Services.
- The provider application needs an **Admin Console with one global MCP Access ON/OFF toggle for the Toyota tenant**. In the initial meeting, the team agreed on **one MCP server with multiple tools**, not five separate MCP servers. The teammate owns the MCP server/adapter; the NMR backend must make the access toggle enforceable through its APIs.
- The key end-to-end demo: Toyota employee asks for stock holdings; the Toyota chatbot invokes an MCP tool which reads the NMR backend; NMR returns authorized synthetic data; admin switches access OFF; the same new tool request is denied; admin turns access ON; the request works again.
- The NMR-side app should be demo friendly, with five tabs and believable sample data, not a full regulated financial platform.
- The specifically mentioned Nomura webpage showed **Shareholding Web Service**, **Defined Contribution Pension Net**, and **Workplace Accumulation NISA Web**, but the team chose the **five broader simulation categories above**. **Do not add NISA as a sixth tab** unless the team changes scope. These five are conceptual mock modules, not a claim that Nomura has five matching public APIs.
- **No live purchases, trades, payroll deductions, settlements, investment advice, or financial transactions.** Show historical records and optional non-executable drafts only.

## 2. What you own and do not own

### Implement (NMR side)
1. Provider backend exposing synthetic workplace finance data via stable versioned REST APIs.
2. Five separate **business modules** with coherent seeded data and tests.
3. NMR admin portal with five service tabs, a tenant overview, an MCP access toggle and request/audit activity.
4. Deterministic authorization enforcement for simulated external MCP callers: **disabled means actual API denial** for new calls, not merely hiding controls.
5. Authentication, tenancy boundaries, errors, request correlation IDs, logs and OpenAPI documentation appropriate to a local demo.
6. Integration handoff docs, a `.env.example`, run commands, seed command, and a sample curl/Postman test.

### Do not implement yet
- Toyota chatbot UI or its LLM prompts.
- MCP server implementation/tool registration; teammate owns this. Coordinate contracts with them before they implement it.
- Another general-purpose AI agent or financial decisioning LLM inside NMR.
- Real Nomura/Toyota accounts or APIs, payments, real share purchases, live custody, financial execution.
- Separate deployment of five independent microservices, cloud production security frameworks, excessive infrastructure.

## 3. Logical architecture

```text
Toyota Employee (hypothetical)
       |
Toyota AI Chatbot / MCP Client                [teammate]
       |
       v
External MCP Server / adapter                [teammate]
       | calls NMR REST APIs with validated demo credentials
       v
+---------------- NMR PROVIDER SIDE -----------------+
| Backend authn/authz + MCP tenant access policy     |
|                     |                              |
|    Five modules:                                    |
|    1. Employee Stock Ownership                      |
|    2. Corporate Pension                             |
|    3. Financial Wellness                            |
|    4. Trust & Custody                               |
|    5. Equity Compensation                           |
|                     |                              |
|    Synthetic database + audit records              |
|                                                    |
| NMR admin UI ------> admin-only settings API       |
|                    [Toyota MCP ON/OFF]             |
+----------------------------------------------------+
```

**Important:** Admin portal and MCP adapter are distinct components. The MCP adapter is not the source of truth for financial records or permissions. The NMR backend enforces the tenant-access setting for every externally originated request.

## 4. Suggested implementation stack

**If the repository already exists, inspect it first and preserve compatible conventions instead of rewriting it.** For greenfield work:
- Provider UI: React + TypeScript + Vite + Tailwind CSS. Clean enterprise-admin layout, white/off-white surface, restrained navy and maroon accents, no generic AI dashboard decoration.
- Backend: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.
- Local database: SQLite for the zero-infrastructure demo; PostgreSQL only if an existing stack requires it. Keep the data access layer portable.
- Testing: pytest + HTTPX for backend; frontend unit tests where meaningful; browser smoke tests if available.
- OpenAPI/Swagger, structured JSON logging, `.env.example`, Docker optional, deterministic seed script.
- Example local development ports: NMR frontend `5173`; NMR backend `8000`. Toyota/MCP can use their own ports. Make everything environment-configurable.

## 5. Required service modules: realistic but limited

Each service should support a useful *read* operation from a hypothetical Toyota employee and a corresponding NMR admin tab. Use fully linked data; no random new values on each request.

| Tab / module | Minimum synthetic records | What an employee can ask | Suggested external read route |
|---|---|---|---|
| Employee Stock Ownership | employee shareholding membership; monthly payroll contribution; purchase lots; shares held; contribution history | “How many company shares do I hold and what did I contribute this year?” | `GET /api/v1/client/me/stock-ownership` |
| Corporate Pension | corporate DC account; employee/employer contributions; balance; allocations | “What is my pension balance and allocation?” | `GET /api/v1/client/me/pension` |
| Financial Wellness | curated article catalog; topic tags; simple educational calculators, not personal recommendations | “Explain the difference between employee shareholding and retirement savings.” | `GET /api/v1/client/wellness/resources?topic=retirement` |
| Trust & Custody | held positions; dividends; corporate-action notices | “Has my latest dividend been credited?” | `GET /api/v1/client/me/custody` |
| Equity Compensation | distinct RSU/option awards; grant dates; vested and unvested units; next vesting events | “When is my next RSU vesting?” | `GET /api/v1/client/me/equity-compensation` |

Business distinctions to preserve:
- Employee stock ownership via contributions/purchases is **not** the same as employer-awarded RSUs/options.
- Pension contributions, pension investments and projections should not be represented as guaranteed outcomes.
- Custody ledger and dividend statements are read-only; avoid simulated money movement.
- Wellness is a resource catalog; it must not fabricate personalized regulated investment advice.
- Mock transaction, purchase and contribution history are **existing synthetic records**. Expose no real execute/trade functionality.

## 6. API contract for teammate integration

Use the following as the **first draft contract**. Document the final route names in `docs/api-contract.md` and publish `/openapi.json` before the chatbot/MCP integration begins.

### External/client-facing routes (for MCP adapter)

```http
GET /api/v1/client/me/stock-ownership
GET /api/v1/client/me/pension
GET /api/v1/client/wellness/resources?topic=retirement
GET /api/v1/client/me/custody
GET /api/v1/client/me/equity-compensation
```

### Provider admin routes

```http
GET   /api/v1/admin/tenants
GET   /api/v1/admin/tenants/{tenantId}/overview
GET   /api/v1/admin/tenants/{tenantId}/employees
GET   /api/v1/admin/tenants/{tenantId}/employees/{employeeId}/service-summary
GET   /api/v1/admin/tenants/{tenantId}/mcp-access
PATCH /api/v1/admin/tenants/{tenantId}/mcp-access
GET   /api/v1/admin/audit-events?tenantId={tenantId}
GET   /health
```

Admin PATCH payload:

```json
{ "enabled": false, "reason": "Demo: revoke external access" }
```

Representative successful external response:

```json
{
  "tenant_id": "toyota-demo",
  "employee_id": "EMP-001",
  "as_of": "2026-11-25",
  "currency": "JPY",
  "shares_held": 125,
  "monthly_contribution_jpy": 20000,
  "total_contributions_jpy": 240000,
  "recent_purchases": [
    {"purchase_date": "2026-11-01", "shares": 4, "amount_jpy": 20000}
  ]
}
```

Numbers above are **illustrative**. Seed entries must be arithmetically consistent; don't build data where monthly contributions, lots, holdings and totals contradict one another.

Error contract:

```json
{
  "error": {
    "code": "MCP_ACCESS_DISABLED",
    "message": "External access is disabled for this client.",
    "request_id": "request-id"
  }
}
```

Suggested status behavior: invalid/expired token `401`; authenticated but unauthorized `403`; disabled tenant `403` with `MCP_ACCESS_DISABLED`; absent record `404`; invalid request `422`. Return `Cache-Control: no-store` on employee financial data and the authorization-sensitive result; propagate an opaque request/correlation ID.

### Proposed future MCP tool mapping (teammate owns these)

```text
get_stock_ownership_summary     -> GET /api/v1/client/me/stock-ownership
get_pension_summary             -> GET /api/v1/client/me/pension
find_financial_wellness_content -> GET /api/v1/client/wellness/resources
get_custody_summary             -> GET /api/v1/client/me/custody
get_equity_compensation_summary -> GET /api/v1/client/me/equity-compensation
```

Do **not** claim these are actual Nomura or Morgan Stanley tools.

## 7. Identity and tenant-access enforcement

Design simple but real demo security rather than a decorative toggle.

- Seed at least two fictionalized tenants (`toyota-demo` and `secondary-demo`) and multiple employees, including one without equity awards. No real employee information.
- Configure an NMR admin identity separately from a client employee or integration identity.
- For the demo, use **signed short-lived test JWTs** (or an equivalent backend-validated identity mechanism) carrying signed `iss`, `aud`, `sub`, `tenant_id`, `employee_id` and relevant role/scope claims. All signing keys are local environment secrets, not in the frontend bundle or Git.
- **Derive tenant/employee identity from the validated token**, not from user-provided prompts, arbitrary request headers, JSON fields or query parameters. External client routes are `/me` for this reason.
- Require scopes/roles separately for admin endpoints and external financial endpoints. The admin toggle is authorized only for NMR admin users.
- For **every client-facing endpoint request**, resolve the validated tenant, check that the tenant's `mcp_enabled` policy is true, then check the employee's access to that service/data. The integration caller's rights must never exceed the represented employee's access. The gateway check remains enforced on actual API calls even if the MCP server still lists tools.
- An external client's cached chat history cannot be revoked retroactively; disabling access prevents **new protected API calls**. Clearly state this in documentation.
- Audit both successful and denied external requests with request ID, tenant, employee, tool/service, outcome, reason and timestamp. Never log raw tokens or secrets.
- The mock environment makes no claim of production-grade security/compliance. A production integration would require proper OAuth, delegated identity, enterprise key management and security review.

## 8. Minimal synthetic data model

Suggested relational entities (combine where reasonable; do not over-normalize for a POC):

```text
Tenant(id, name, fictional_demo_flag)
Employee(id, tenant_id, display_name, active)
TenantMcpSettings(tenant_id, enabled, changed_by, changed_at)
ShareholdingAccount(employee_id, plan_id, shares_held)
PayrollContribution(employee_id, month, amount_jpy)
SharePurchase(employee_id, date, shares, price_jpy, amount_jpy)
PensionAccount(employee_id, balance_jpy, type)
PensionContribution(employee_id, date, employee_amount, employer_amount)
PensionAllocation(employee_id, asset_class, percentage)
WellnessResource(id, title, topic, description, content)
CustodyPosition(employee_id, instrument, quantity)
Dividend(employee_id, payment_date, amount_jpy, status)
CorporateAction(id, instrument, title, effective_date)
EquityGrant(id, employee_id, award_type, granted_units, granted_date)
VestingEvent(grant_id, vest_date, units, status)
AuditEvent(id, request_id, actor, tenant_id, action, outcome, reason, created_at)
```

Seed deterministic scenarios: one employee with monthly contributions and shares; one with pension and dividends; one with future RSU vesting; one without equity compensation; another tenant's employee to test isolation. Use a fixed reference date or inject the clock in tests so vesting and dividend tests do not change unpredictably across dates.

## 9. Provider UI design

A single well-designed NMR web application with:

- **Overview**: mock tenant selector or focused Toyota tenant view, total synthetic accounts, recent access/activity, clear 'Demo / synthetic' label.
- **Five service tabs**: browse records, choose a demo employee, view realistic tables/timelines with totals/units/dates/currency, and empty/error states. The tabs use **real backend APIs**, not hardcoded frontend arrays.
- **Admin > MCP Access**: one obvious, working on/off toggle for tenant Toyota; state persistence, last changed metadata and explanatory status.
- **Admin > Audit**: timestamped permitted and denied external requests; filter by tenant/result.
- Clean enterprise style: restrained typography, white/slate/navy, minimal color, no marketing infographic widgets, no excessive chart decorations or nonfunctional buttons.
- Responsive layout for laptop-first review. Empty states and API errors are visible and meaningful.

For provider administrator data browsing, use separately authorized admin routes or an authorized view. Do not incorrectly make the admin UI impersonate an external employee or bypass tenant policy to test MCP.

## 10. Build steps for Codex (perform in order)

### Step 0 — Inspect and plan
- Inspect repository, existing tech stack, scripts, routes, dependencies, styles, tests, and README. Preserve existing work; do not overwrite unrelated code.
- Briefly report a proposed file tree, design decisions and expected commands. Record ownership boundary (NMR only).
- Create `docs/api-contract.md` and an implementation checklist. No new MCP server or Toyota client.

### Step 1 — Data and service layer
- Implement DB schema and deterministic seed data.
- Implement five independently testable business modules. Ensure results are derived from stored records, never random at request time.
- Business logic stays outside API routes so a future MCP adapter can consume it without reimplementation.

### Step 2 — REST API + security
- Implement external client endpoints and admin endpoints with Pydantic schemas.
- Validate mock credentials, roles, tenant scopes and employee isolation.
- Enforce `mcp_enabled` on every new client API request. Generate structured audit events and documented errors.
- Serve OpenAPI and export example responses.

### Step 3 — NMR admin UI
- Build overview, five service tabs, admin MCP toggle, audit page.
- Wire to backend endpoints; ensure loading, success, permission denied and failures render correctly.
- No pretend network operations, static fake API results or decorative toggle.

### Step 4 — Automated testing
- Unit tests for each service and its domain invariants.
- API tests for all client and admin routes, token failures, authorization, cross-tenant leakage, unknown employee, no awards, and stale/mock data behavior.
- Toggle-on/off/on integration test: same valid employee token, request works when enabled, returns `403 MCP_ACCESS_DISABLED` after admin disables, works after re-enable.
- Unauthorized admin toggle attempt must be rejected; state must persist in DB.

### Step 5 — Handoff + demo readiness
- Add README with prerequisites, `.env.example`, seed command, run commands, test commands, example tokens, curl requests and screenshot/demo steps.
- Share `docs/api-contract.md` and `/openapi.json` with teammate implementing MCP server/Toyota client.
- Demonstrate service response and denial using direct HTTP calls **before** MCP integration.
- Avoid scope expansion. At the end, give changed files, running URLs, tests executed/results, limitations and any integration questions for the teammate.

## 11. Required acceptance tests

1. Five tabs load meaningful, correct synthetic data from a running NMR backend.
2. Admin can switch Toyota MCP access ON and OFF, and state persists.
3. External `GET /api/v1/client/me/stock-ownership` succeeds for a permitted Toyota employee while enabled.
4. The **same** request returns `403 MCP_ACCESS_DISABLED` once disabled—even if the external client ignores UI/tool-discovery information.
5. Re-enabling restores authorized access without restarting processes.
6. A second tenant is unaffected by Toyota's toggle; its data never leaks to Toyota.
7. A regular employee cannot call the admin toggle endpoint.
8. Wellness resources, custody dividends, pension summary and equity vesting all return distinct, validated responses.
9. Denied/successful external requests are visible in NMR admin audit log without leaking secrets.
10. Project runs locally with reproducible commands and integration instructions; tests pass.

## 12. Suggested live demo script

1. Open NMR Admin and show all five finance tabs with sample records.
2. Show Toyota tenant's MCP access enabled.
3. Teammate asks Toyota chatbot: **“How many company shares do I hold, and what was my latest contribution?”**
4. External MCP tool calls NMR client API; result is returned with actual seeded shares/contributions.
5. NMR admin turns **MCP Access OFF**.
6. Teammate repeats the same question; new backend invocation fails with `MCP_ACCESS_DISABLED`. Show denied audit event.
7. NMR admin turns **MCP Access ON**; request succeeds.
8. Optionally run a pension or vesting question to show same MCP server can access another approved service.

## 13. Copy-paste kickoff instruction for Codex

> You are the engineering owner for **NMR provider-side Workplace Finance POC**. Read `NMR_Workplace_Finance_POC_Codex_Implementation_Brief.md` in full and implement it in the current repository. Preserve existing code. Begin with an inspection and a concise implementation plan, then create the backend domain models, synthetic seed data, stable REST API and security/admin toggle, followed by the five-tab NMR admin UI, audit log, tests, and handoff documentation. **Do not build the Toyota chatbot, MCP server or any actual financial execution.** Ask for input only if a blocker makes it impossible to proceed; otherwise choose practical defaults. Execute tests, fix failures and report the exact run commands and open issues. The single most important acceptance test is: when an NMR administrator disables access for Toyota, the same otherwise-valid external employee request is rejected by the backend, and when re-enabled it succeeds again.

## 14. Items to align with teammates, not assumptions

- Final HTTP host/ports for MCP adapter → NMR backend.
- Identity/token exchange in the local POC. Agree on claims, signature verification, issuer/audience and how the adapter obtains a permitted employee context.
- External tool names/arguments and response payload contracts.
- Whether NMR admin should show only one tenant (Toyota) or allow switching among demo tenants.
- Whether all five tools need to run in the first video, or one full demo plus four service lookups is sufficient.

**Key principle:** The value of this POC is not a chatbot or an ornamental MCP toggle. It is an agent-accessible workplace-finance provider whose access is truly controlled and whose responses come from coherent, authorized mock records.
