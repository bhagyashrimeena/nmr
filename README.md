# NMR Workplace Finance

NMR's provider-side application for five workplace finance services. The React portal connects to a FastAPI backend with persisted tenant settings, financial and workflow records, and request audit. It runs locally with synthetic clients and participants. The Toyota chatbot and MCP adapter are outside this repository.

**Implementation status:** All five provider workbenches, the participant directory, operational reports, stock payroll and purchase controls, and master/per-service external access switches are implemented. The backend remains the authority for financial state and permissions. The [current limits](#current-limits) matter when planning the Toyota integration.

## Layout

- `backend/app/`: API, domain workflows, database models, migrations, access control, audit, and fixed local records.
- `backend/tests/`: API, domain, policy, and tenant-isolation tests.
- `frontend/`: React and TypeScript provider portal.
- `docs/v2-api-contract.md`: endpoint, identity, permission, error, and audit contract for MCP integration.
- `docs/v2-implementation-status.md`: architecture, completed milestones, and remaining work.
- `docs/verification-report.md`: source-backed business scenarios, screenshots, verification results, and current limits.
- `docs/specialist-workbenches.md`: service-by-service portal map and browser verification.
- `docs/api-contract.md`: original V1 contract.
- `docs/openapi.json`: exported OpenAPI specification for both API versions.

## Start locally (Windows PowerShell)

Requires Python 3.12+, Node.js 22 (the CI version), and free ports 8000 and 5173. Run each terminal from the repository root. The sample `.env` permits both `localhost:5173` and `127.0.0.1:5173` as portal origins.

In one PowerShell terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env: replace NMR_JWT_SECRET with a random local value of at least 32 characters.
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/health` for `{"status":"ok"}`. Startup creates additive schema tables and loads repeatable records without resetting existing access settings. It creates three clients and 256 participants. The default SQLite file is `backend/nmr_demo.db`; local state changes survive a restart. If compiled SQLAlchemy extensions are blocked by Windows policy, set `$env:DISABLE_SQLALCHEMY_CEXT='1'` and reinstall SQLAlchemy with `--no-binary SQLAlchemy`.

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. With the supplied local configuration, sign in as `nmr-admin` using password `123456`. The portal reads from `http://127.0.0.1:8000` by default; override with `VITE_API_BASE` in `frontend/.env`. Keep the supplied credentials and this configuration on localhost.

## What is available

The provider portal opens each service in a **purpose-built financial operations workbench**, using persisted V2 records:

| Service | Internal operational workspace |
| --- | --- |
| Employee Stock Ownership | Payroll batch pipeline, purchase allocations, transfer processing and reconciliation cases |
| Corporate Pension | Dated fund valuations, investment allocations, contribution instructions and exceptions |
| Financial Wellness | Editorial content approvals, published benefit rules and seminar programme |
| Trust & Custody | Transfer settlement monitor, position details, corporate actions and dividend processing |
| Equity Compensation | Grant register, vesting timeline, plan reserve and release review |

Each workbench links to its actual backend operations and separately groups **Provider workspace** from **Participant account** views. The master MCP switch and five tenant-specific service switches remain enforced by the provider backend, not by the UI.

The five service areas also have detailed records and operator views:

- Stock ownership: plan, membership, payroll posting, purchase allocation, transfer review, and reconciliation cases.
- Pension: fund positions and NAV, contribution records, future allocation instructions, and exceptions.
- Equity compensation: grant reserve, vesting tranches, release review, and option exercise drafts.
- Trust and custody: account inventory, corporate actions, dividend entitlement and cash, and linked transfer status.
- Financial wellness: approved education, tenant benefit rules, seminars, and a reproducible savings calculator.

The portal also has a searchable participant directory, client service agreements, a cross-service work queue, and dated operational reports. Stock operations can inspect rejected payroll lines and post an evidenced correction into a separate batch. The source batch and its resolution history remain visible. Provider operators can be scoped to one tenant and service; corporate plan administrators have an aggregate-only reporting route.

MCP Access Management stores one master and five service switches per tenant. New external calls are checked against both switches and employee permissions. Admin browsing stays available when external access is off. V1 routes remain available; V2 routes use `/api/v2` and are described in [the V2 contract](docs/v2-api-contract.md). OpenAPI is served at `/docs` and `/openapi.json`.

The Toyota records include `EMP-001`, `EMP-002`, and `EMP-003`; `SEC-001` belongs to Sakura Mobility. Additional participant IDs begin `TYO-`, `SAK-`, and `AST-` for Toyota, Sakura Mobility, and Asterfield Industries. V2 records are fixed as of 26 November 2026. The original summary records use 25 November 2026.

## MCP integration

Use the documented `/api/v2/client/...` endpoints for employee-facing tools. The NMR provider does **not** include the Toyota chatbot or MCP server. One MCP server may expose tools across the five services. Do not expose `/api/v1/admin/...` or `/api/v2/admin/...` through those tools.

Client requests require a signed employee JWT with tenant and employee claims. The backend checks the employee's service eligibility, the tenant's master switch, and that service's switch on every call. Neither a URL parameter nor an LLM response may select a different employee. For a local read-only integration check, run from `backend/` after starting the API:

```powershell
$token = .\.venv\Scripts\python.exe -m app.tokens --tenant toyota-demo --employee EMP-001
Invoke-RestMethod 'http://127.0.0.1:8000/api/v2/client/me/shareholding/summary' -Headers @{ Authorization = "Bearer $token" }
```

Turning stock access off should return `403 SERVICE_ACCESS_DISABLED` for that route while another enabled service continues to work; turning the master switch off should deny all five services. The switches do not erase individual settings. The response body contains a stable error code and request ID, and protected calls are audited. Draft requests need a separate `draft:<service>` scope and an `Idempotency-Key`; they create requests inside NMR, not external financial transactions. Read [the V2 API contract](docs/v2-api-contract.md) and [OpenAPI](docs/openapi.json) before implementing tools. Local token minting shares the backend signing secret and is a development aid, not delegated production authentication.

## Verify

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m app.smoke
cd ..\frontend
npm run build
npm run smoke:browser  # five-workbench Chromium check
```

The browser smoke test requires both servers and Chrome on Windows (or an installed Chromium on Linux). It saves screenshots under `docs/screenshots/specialist/`. The HTTP smoke test restores access settings after its ON/OFF/ON sequence. GitHub Actions also runs backend tests, the frontend build, and a browser smoke check; see `.github/workflows/v2-financial-workflow-checks.yml`.

## Current limits

- Pension switching remains a draft workflow; it does not rebalance existing positions. Stale NAV exception handling needs more depth.
- Custody settlement failure and recovery, equity PSU certification and employment-event rules, and wellness content revision history remain incomplete.
- The exact 149.75-to-49.75 shareholding/custody scenario is not seeded. Existing opening inventories have separate sources.
- The Toyota chatbot-to-MCP-to-provider path has not been tested end to end. The provider API and access controls are ready for that separate integration.
- There is no real customer information or external financial execution. Local authentication, SQLite, and shared-secret token minting are for workstation evaluation. A deployed integration requires delegated identity, managed secrets, rate limits, managed migrations, monitoring, and security review. Switches govern new calls; they cannot revoke responses already returned.

For service-specific findings and source references, see [the verification report](docs/verification-report.md) and [implementation status](docs/v2-implementation-status.md).
