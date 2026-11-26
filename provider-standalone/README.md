# NMR Workplace Finance — Provider-Side POC

A **fully runnable, provider-side application** for a proposed cross-enterprise workplace-finance MCP demonstration. NMR is a fictional financial institution and Toyota is a *hypothetical* corporate demo tenant; neither a real client relationship nor an actual Nomura deployment is implied.

The project implements the **right-hand side of the team architecture**: a detailed internal operations portal, five synthetic financial-service domains, versioned APIs, persistent master and per-service access controls, and an audit trail. It does **not** implement the Toyota chatbot or MCP adapter, which remain teammates' responsibility.

## Functional scope

| Service | Synthetic domain functions | Example external GET |
|---|---|---|
| Employee Stock Ownership | Plan enrolment, payroll contribution history, employer incentive, settled purchase lots, share holdings and valuation with reconciliation | `/api/v1/client/me/stock-ownership` |
| Corporate Pension | Corporate DC balance bridge, employee/employer contributions, portfolio allocations, assumption-driven long-term illustrative projection | `/api/v1/client/me/pension` |
| Financial Wellness | Eight curated educational records, topics, completion progress and search/filtering | `/api/v1/client/wellness/resources` |
| Trust & Custody | Custodied synthetic positions, paid/announced dividends, corporate actions and historic settlement records | `/api/v1/client/me/custody` |
| Equity Compensation | Distinct RSU/option awards, quantity reconciliation, exercise prices, past and future vesting dates | `/api/v1/client/me/equity-compensation` |

**Admin:** choose tenant and employee, inspect all five detailed service views, adjust individual service permissions, switch master MCP access, test each endpoint using a signed employee demo token, inspect audit log. Disabling external access **never blocks NMR internal admin views**.

**Main proof:** The same valid client employee request returns 200 when allowed, `403 SERVICE_ACCESS_DISABLED` for its disabled service, or `403 MCP_ACCESS_DISABLED` when the master switch is off. Other enabled services and other tenants remain unaffected.

## Quick start — Windows / PowerShell

```powershell
cd path\to\nmr-workplace-finance-poc
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:NMR_JWT_SECRET="set-a-unique-local-demo-secret-minimum-32-characters"
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **http://127.0.0.1:8000/** for the NMR portal, **http://127.0.0.1:8000/docs** for Swagger, or **http://127.0.0.1:8000/openapi.json** for the contract.

## Quick start — macOS / Linux

```bash
cd nmr-workplace-finance-poc
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export NMR_JWT_SECRET="set-a-unique-local-demo-secret-minimum-32-characters"
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Windows quick alternative: double-click `start_nmr_windows.bat` (it creates a virtual environment, installs dependencies, generates a temporary local secret, and starts the app on port 8000).

No Node.js installation is needed for this standalone package.** The admin portal is built with dependency-free browser JavaScript and CSS and served by FastAPI. This is intentional to make the POC immediately executable; see `docs/MERGE_GUIDE.md` if you already have a React/Vite project and want to merge this functionality.

The SQLite database (`nmr_demo.sqlite3` by default) is created and seeded automatically on first start. All identities and figures are synthetic, deterministic and suitable for reproducible demonstration. The baseline is as of **26 November 2026**.

## A 2-minute demo without the MCP adapter

1. Open NMR and visit **MCP Access Management**. The master access switch and five service switches are ON.
2. Click **Test API** next to *Employee Stock Ownership*; the UI performs a real external request under a signed demo employee identity, and displays HTTP **200** with the returned financial records.
3. Switch *Employee Stock Ownership* OFF, leaving *Corporate Pension* ON.
4. Click **Test API** again for Stock Ownership. The backend now returns HTTP **403 `SERVICE_ACCESS_DISABLED`**.
5. Click **Test API** for Pension; it still returns HTTP **200**.
6. Re-enable Stock Ownership. Test it again to see HTTP **200**.
7. Turn the master switch OFF. Every external client request now returns **403 `MCP_ACCESS_DISABLED`**, although the five internal NMR tabs remain available.
8. Open **Audit Trail** to see the configuration changes and rejected/successful external calls.

## Real API test via PowerShell

Get a local demo employee token (the test identity endpoint exists **only for local demo mode**, never production):

```powershell
$session = Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/api/v1/demo/session -ContentType 'application/json' -Body '{"persona":"toyota-001"}'
$headers = @{ Authorization = "Bearer $($session.access_token)" }
Invoke-RestMethod http://127.0.0.1:8000/api/v1/client/me/stock-ownership -Headers $headers
```

For full admin and MCP-developer examples see `docs/API_CONTRACT.md`.

## Run tests

```bash
python -m pytest -q tests/test_provider.py
```

The tests cover five service ON/OFF controls, master ON/OFF, tenant separation, admin-only mutations, token validation, account enrollment edge cases, financial reconciliation, wellness filtering, audit records, OpenAPI and state persistence.

## Architecture

```text
[Toyota employee chatbot / MCP client]                 OTHER TEAM
                 |
         [MCP adapter / server]                        OTHER TEAM
                 | validated employee-scoped credential
                 v
+-------------------------- NMR PROVIDER -------------------------------+
| Authenticated REST endpoints -> master policy -> per-service policy   |
|                                -> tenant / employee entitlement       |
|                                                                       |
|  Internal NMR Admin UI -> admin-only configuration APIs               |
|         |                                                             |
|         +-- employee stock ownership                                  |
|         +-- corporate pension                                          |
|         +-- financial wellness                                         |
|         +-- trust & custody                                            |
|         +-- equity compensation                                        |
|                                                                       |
|  SQLite synthetic employee data + persistent policies + audit events  |
+-----------------------------------------------------------------------+
```

A thin MCP server can map tool calls to NMR's **existing business REST services**, with no duplicate business calculations in the MCP process. Its tool discovery may filter inaccessible services, but the **actual read operations are always authorized by NMR**.

## Configuration

Environment variables:

- `NMR_DATABASE_URL`: SQLite URL (default `sqlite:///./nmr_demo.sqlite3`).
- `NMR_JWT_SECRET`: signing key for **synthetic local demo** tokens. Set to a unique string of at least 32 characters. Do not commit it.
- `NMR_DEMO_MODE`: default `true`; set `false` to remove the demo token-issuance endpoint. Note: without a separate real auth integration, disabling demo mode also makes the UI inoperable for interactive use.
- `NMR_CORS_ORIGINS`: comma-separated origins for any external browser test frontend.

**Important security limitations:** `/api/v1/demo/session` deliberately allows access to fake identities without passwords and exists solely for local testing. Run on `127.0.0.1` only; **never publish this app to the internet or a company network with demo mode enabled**. JWT credentials in this prototype are not a substitute for corporate SSO, per-user delegated OAuth, production key management, endpoint-level scopes, regulatory controls or penetration testing. Test data is fake, and all APIs are strictly read-only for external employees. Financial execution is intentionally absent. Real bank integrations require appropriate security, privacy, business ownership and approval reviews.

## Files

- `app/main.py` — API, authorization enforcement and admin routes.
- `app/seed.py` — deterministic synthetic test records; reset mode supported for automated tests.
- `app/domain.py` — financial calculations and service projections.
- `app/models.py` — database models and audit events.
- `app/security.py` — demo JWT identities and validation.
- `static/` — responsive internal admin frontend (no build step).
- `tests/` — backend tests.
- `docs/API_CONTRACT.md` — exact endpoints and handoff instructions.
- `docs/MERGE_GUIDE.md` — merging into an already-built React/FastAPI repository.

## Team ownership and next step

**Built here:** NMR portal and backend (right-side provider scope). **Not built here:** Toyota chatbot and MCP server (left side and integration), plus any production bank data connection. To complete the team demonstration, the MCP developer should consume `docs/API_CONTRACT.md`, then map a stock-holdings tool to NMR's `/api/v1/client/me/stock-ownership` with valid employee identity and authorization. Once their adapter is available, run the on/off/on demo end to end.
