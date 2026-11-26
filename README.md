# NMR Workplace Finance POC · provider side

Fictional NMR workplace finance provider, with five read-only service modules, a local administrator portal, signed demo JWTs, persistent MCP access control, and request audit. Toyota is a hypothetical client in this demonstration. All people and financial records are synthetic. The Toyota chatbot and MCP adapter are separate teammate work and are not included here.

## Project layout

- `backend/app/`: FastAPI routes, SQLAlchemy models, deterministic seed, service logic, JWT authorization, audit.
- `backend/tests/`: domain and API tests, including ON/OFF/ON and tenant isolation.
- `frontend/`: React/TypeScript provider administrator portal.
- `docs/api-contract.md`: MCP adapter handoff contract. `docs/openapi.json`: exported OpenAPI snapshot.
- `docs/implementation-plan.md`: architecture and build sequence.

## Prerequisites

Python 3.12+ and Node.js 20+. Local ports 8000 and 5173 must be free.

## Start the backend (PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env: set a random NMR_JWT_SECRET of at least 32 characters and an NMR_ADMIN_PASSWORD.
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On Windows machines whose application policy blocks compiled SQLAlchemy extensions, install the pure Python build after the requirements install:

```powershell
$env:DISABLE_SQLALCHEMY_CEXT='1'
.\.venv\Scripts\python.exe -m pip install --force-reinstall --no-binary SQLAlchemy 'SQLAlchemy>=2.0,<2.1'
```

The database file defaults to `backend/nmr_demo.db` and persists policy changes and audit records across server restarts. `python -m app.seed` is idempotent for an existing database. To start a fresh demo, stop the server, remove the local `nmr_demo.db`, and rerun the seed command.

## Start the portal (another PowerShell terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Sign in as `nmr-admin` with the `NMR_ADMIN_PASSWORD` in `backend/.env`. The portal calls the backend at `http://127.0.0.1:8000`; set `VITE_API_BASE` in a local `frontend/.env` to change that. Choose a tenant and employee to browse the five tabs. The MCP Access page changes the database setting; Audit Records shows external API activity.

## Verify the API

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m app.smoke
```

The smoke command uses real HTTP against the running backend, verifies stock `200 → 403 MCP_ACCESS_DISABLED → 200`, checks the second tenant and audit, then restores the prior Toyota policy. It does not print credentials.

For a manual external request, mint a short-lived employee JWT locally:

```powershell
$token = .\.venv\Scripts\python.exe -m app.tokens --tenant toyota-demo --employee EMP-001
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/client/me/stock-ownership' -Headers @{ Authorization = "Bearer $token" }
```

The first employee has 120 shareholding-plan shares and ¥240,000 of recorded payroll contributions. `EMP-002` has no equity awards. `EMP-003` has no shareholding access. `SEC-001` belongs to the separate fictional tenant. All results are fixed as of 25 November 2026.

OpenAPI: `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/openapi.json`. See [docs/api-contract.md](docs/api-contract.md) for token claims, routes, errors, examples, and the proposed MCP tool mapping.

## Live demonstration

1. Sign in to the provider portal and inspect the five tabs for Aiko Mori (`EMP-001`).
2. Show Toyota MCP Access is enabled, then have the teammate's MCP adapter call the stock route with an employee JWT.
3. Disable access in the NMR portal. Repeat the **same** new external request: the backend returns `403 MCP_ACCESS_DISABLED`.
4. Open Audit Records and refresh to see the denied request. Enable access again and repeat: it succeeds without a server restart.

## Boundaries and limitations

This local POC has fixed historical data, no financial execution, and no real customer information. Its local password login and shared-secret demo JWT minting are suitable only for the demonstration. A production integration would require delegated OAuth, enterprise key handling, rate limits, migrations, operational monitoring, and a security review. The access switch prevents new protected API calls; it cannot erase already returned responses or chat history. End-to-end chatbot/MCP verification remains dependent on the teammate's separate components.
