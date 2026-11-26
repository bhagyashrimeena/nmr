# NMR Workplace Finance

Provider administration for five workplace finance services, with a React portal, authenticated APIs, persistent master and per-service external access controls, and request audit. The Toyota chatbot and MCP adapter are separate components and are not included here.

## Project layout

- `backend/app/`: FastAPI routes, SQLAlchemy models, deterministic seed, detailed service calculations, JWT authorization, policy changes and audit.
- `backend/tests/`: domain and API tests, including five independent ON/OFF/ON sequences, master policy, and tenant isolation.
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

The database file defaults to `backend/nmr_demo.db` and persists master/service settings, learning progress, policy changes and audit records across server restarts. `python -m app.seed` is idempotent and adds the detailed-service tables and records to an existing initial POC database. To start a fresh demo, stop the server, remove the local `nmr_demo.db`, and rerun the seed command.

## Start the portal (another PowerShell terminal)

```powershell
cd frontend
npm install
npm run dev
```

For a local Chrome smoke test and captured provider screenshots, keep both servers running and run `npm run smoke:browser` from `frontend/`. It checks the five screens, subviews, search, calculators, empty state, service toggle persistence and audit. The images are saved under `docs/screenshots/`.

Open `http://127.0.0.1:5173`. Sign in as `nmr-admin` with the `NMR_ADMIN_PASSWORD` in `backend/.env`. The portal calls the backend at `http://127.0.0.1:8000`; set `VITE_API_BASE` in a local `frontend/.env` to change that. Choose a tenant and employee to browse the five services, each with detailed subviews. Corporate Clients shows tenant and employee scope. MCP Access Management has one master switch and five separate service switches for the selected tenant. Audit Logs shows external calls; policy history shows previous and new values.

## Verify the API

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m app.smoke
```

The smoke command uses real HTTP against the running backend. It verifies stock `200 → 403 SERVICE_ACCESS_DISABLED → 200` while pension remains available, then checks that the master switch blocks both. It verifies the second tenant and audit, and restores the prior Toyota settings. It does not print credentials.

For a manual external request, mint a short-lived employee JWT locally:

```powershell
$token = .\.venv\Scripts\python.exe -m app.tokens --tenant toyota-demo --employee EMP-001
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/client/me/stock-ownership' -Headers @{ Authorization = "Bearer $token" }
```

The first employee has 120 shareholding-plan shares and ¥240,000 of recorded payroll contributions. `EMP-002` has no equity awards. `EMP-003` has no shareholding access. `SEC-001` belongs to the separate fictional tenant. All results are fixed as of 25 November 2026.

OpenAPI: `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/openapi.json`. See [docs/api-contract.md](docs/api-contract.md) for token claims, routes, errors, examples, and the proposed MCP tool mapping.

## Access control walkthrough

1. Sign in to the provider portal and inspect the five detailed services for Aiko Mori (`EMP-001`). Stock statements, pension valuations, wellness search and calculators, custody settlements, and RSU/option vesting all come from the backend.
2. Show Toyota master and stock access enabled, then call the stock route with an employee JWT.
3. Disable **only stock** in MCP Access Management. Repeat the same request: the backend returns `403 SERVICE_ACCESS_DISABLED`, while pension still succeeds.
4. Re-enable stock and repeat: it succeeds. Disable the master switch: all five external service routes fail with `MCP_ACCESS_DISABLED`, but admin browsing still works.
5. Re-enable master. Open Audit Logs and policy change history to show request IDs and previous/new settings.

## Boundaries and limitations

This local POC has fixed historical data, no financial execution, and no real customer information. Wellness learning progress is the only mutable employee-service record in the admin portal. Its local password login and shared-secret demo JWT minting are suitable only for the demonstration. A production integration would require delegated OAuth, enterprise key handling, rate limits, schema migrations, operational monitoring, and a security review. Policy switches prevent new protected API calls; they cannot erase already returned responses or chat history. End-to-end chatbot/MCP verification remains dependent on the teammate's separate components.
