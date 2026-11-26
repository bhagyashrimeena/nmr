# NMR Provider — Five Specialist Workbenches

Date: 26 November 2026. Branch: `feat/five-specialist-workbenches`.

## Purpose

NMR uses one provider-side design system with five operationally distinct financial workspaces. These are **internal provider screens**, not Toyota employee screens. The workflows use the existing FastAPI V2 services and synthetic records; no unauthorised MCP tool or real financial capability has been added.

| Service | Default workspace | Source route | Live drill-down |
| --- | --- | --- | --- |
| Employee Stock Ownership | Payroll stage pipeline, purchase batches, payroll exceptions and selected batch details | `/api/v2/admin/tenants/{tenant}/shareholding/operations` | Payroll batches; purchase cycles; exceptions |
| Corporate Pension | Participant fund allocations, dated NAV product catalog, contribution instructions and exceptions | `/api/v2/admin/tenants/{tenant}/pension/operations` | Fund positions; investment funds; instruction queue; projections |
| Financial Wellness | Editorial approval queue, approved content, benefit-source rules and seminars | `/api/v2/admin/tenants/{tenant}/wellness/operations` | Content library; benefit rules; seminars |
| Trust & Custody | Dense settlement transfer monitor, correlated settlement confirmations, corporate actions and dividends | `/api/v2/admin/tenants/{tenant}/custody/operations` | Settlement monitor; action register; dividend processing |
| Equity Compensation | Authorized/issued/reserved units, grant register, individual vesting tranches and release queue | `/api/v2/admin/tenants/{tenant}/equity/operations` | Grant register; vesting schedule; release queue; equity exceptions |

## Interaction design

- Each financial service opens to **Workbench** as its default view. Provider operations and participant account views are grouped separately, so staff do not have to scan one long list of mixed tabs.
- Every workbench uses current tenant-scoped V2 operational data and an as-of date. No hardcoded financial KPI values are introduced.
- Search and award-type filters operate on available source records; selected record panels follow the current filter.
- Primary actions navigate into the existing business workflows. Financial rules and state transitions continue to be enforced in the FastAPI provider, never in frontend code.
- The shared NMR shell, typography, table rules, statuses and restrained burgundy accent remain consistent across all five domains.
- The fixed “Demo Environment” indicator remains visible at the app level.

## What was intentionally not changed

- Real financial calculations, stock/pension/custody/equity business rules, audit, and all master/per-service MCP authorization controls.
- External employee or chatbot tool permissions. Provider-admin endpoints are not exposed as MCP tools.
- The separate Toyota chatbot and MCP integration application.

## Verification

`cd backend && python -m pytest -q`

`cd frontend && npm ci && npm run build`

With API and portal running locally and a configured demo admin password:

`cd frontend && npm run smoke:workbenches`

The browser smoke opens all five workbenches, checks for real operation rows, drills into the corresponding operational screen, and saves screenshots to `docs/screenshots/specialist/`.

GitHub Actions runs the backend regression suite, the TypeScript/Vite build and the browser smoke with a synthetic local backend. Browser screenshots are attached as CI artifacts if the run succeeds.

## Limitations

These five workbenches improve **business-specific UI and navigation**; they do not complete the remaining V2 financial domain roadmap. PSU performance certification, pension switch execution simulation, custody failure recovery, content-version history, and end-to-end external MCP/ChatGPT integrations remain future milestones.

NMR and the corporate tenants are fictional. No production financial services, client data, orders or transfers are connected.
