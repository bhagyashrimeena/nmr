# NMR Workplace Finance

Provider administration for five workplace finance services. The React portal connects to a FastAPI backend with persistent tenant access settings, operational records, and request audit. The Toyota chatbot and MCP adapter are separate components.

## Layout

- `backend/app/`: API, domain workflows, database models, migrations, access control, audit, and fixed local records.
- `backend/tests/`: API, domain, policy, and tenant-isolation tests.
- `frontend/`: React and TypeScript provider portal.
- `docs/v2-api-contract.md`: V2 external handoff and workflow contract.
- `docs/v2-implementation-status.md`: architecture, completed milestones, and remaining work.
- `docs/api-contract.md`: original V1 contract.
- `docs/openapi.json`: exported OpenAPI specification for both API versions.

## Start locally

Requires Python 3.12+, Node.js 20+, and ports 8000 and 5173.

In one PowerShell terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Replace NMR_JWT_SECRET in .env with a random string of at least 32 characters.
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Startup creates additive V2 tables and loads repeatable service records without resetting existing access settings. The default SQLite file is `backend/nmr_demo.db`. If compiled SQLAlchemy extensions are blocked by Windows policy, set `$env:DISABLE_SQLALCHEMY_CEXT='1'` and reinstall SQLAlchemy with `--no-binary SQLAlchemy`.

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. With the supplied local configuration, sign in as `nmr-admin` using password `123456`. Keep this application on localhost. The portal reads from `http://127.0.0.1:8000` by default; override with `VITE_API_BASE` in `frontend/.env`.

## What is available

The five service areas have detailed records and operator views:

- Stock ownership: plan, membership, payroll posting, purchase allocation, transfer review, and reconciliation cases.
- Pension: fund positions and NAV, contribution records, future allocation instructions, and exceptions.
- Equity compensation: grant reserve, vesting tranches, release review, and option exercise drafts.
- Trust and custody: account inventory, corporate actions, dividend entitlement and cash, and linked transfer status.
- Financial wellness: approved education, tenant benefit rules, seminars, and a reproducible savings calculator.

MCP Access Management stores one master and five service switches per tenant. New external calls are checked against both switches and employee permissions. Admin browsing stays available when external access is off. V1 routes remain available; V2 routes use `/api/v2` and are described in [the V2 contract](docs/v2-api-contract.md). OpenAPI is served at `/docs` and `/openapi.json`.

The Toyota records use employee IDs `EMP-001`, `EMP-002`, and `EMP-003`; `SEC-001` belongs to the separate Sakura tenant. V2 records are fixed as of 26 November 2026. The original summary records use 25 November 2026.

## Verify

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m app.smoke
cd ..\frontend
npm run build
npm run smoke:browser
```

The browser smoke test requires both servers and saves screenshots under `docs/screenshots/`. The HTTP smoke test restores access settings after its ON/OFF/ON sequence.

## Operational boundary

The local application uses fixed test records and has no real customer information or financial execution. State changes stay inside its database. The local password and shared-secret JWT minting are intended for workstation use. A deployed integration requires delegated identity, managed secrets, rate limits, managed migrations, monitoring, and security review. The switches govern new calls; previously returned responses cannot be revoked. The chatbot/MCP path still needs verification when the teammate's components are connected.
