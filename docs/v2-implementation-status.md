# V2 implementation status and architecture

Source blueprint: `NMR_Workplace_Finance_V2_Functional_Blueprint.md`. This work extends the existing React/FastAPI application and keeps `/api/v1` available. The provider application remains separate from the Toyota chatbot and MCP server.

## Architecture and file structure

- `backend/app/v2_models.py`: normalized operational tables and append-only ORM guard for financial events.
- `backend/app/migrations.py`: additive SQLite table creation and schema version record. Startup invokes it before seeding; existing V1 tables and policy settings remain in place.
- `backend/app/v2_*_seed.py`: repeatable fixed records per service. The stock seed also creates legal entities and employee profiles.
- `backend/app/{stock,pension,equity,custody,wellness}_v2.py`: `/api/v2` routers. Client handlers use a shared signed-identity and tenant/service policy dependency. Admin handlers use separate admin permissions.
- `frontend/src/*Operations.tsx`: operator views for each service. They read V2 routes. The existing overview views continue to use V1 summaries.
- `backend/tests/test_*_v2.py` and `backend/tests/test_realism_qa.py`: domain, identity, policy, API, and financial operations verification.
- `docs/v2-api-contract.md`: teammate handoff; `docs/openapi.json`: exported OpenAPI snapshot.

The data path is: signed employee token -> master/service/employee policy -> tenant-scoped service query -> event or domain state -> response and operation audit. Admin review routes update workflow states and write an audit event. Financial journal amounts use `Decimal`; stock and custody movement on a completed transfer shares a correlation ID.

## Implemented workflow milestones

1. Foundation: additive schema, legal entities, employee profiles, event journal, reconciliation cases, workflow records, statements, and operation audit.
2. Stock: payroll receive/validate/post with dated rule provenance, purchase create/price/settle/allocate, fractional beneficial interests, whole-share transfer eligibility, recipient-account checks, settlement-confirmed transfer posting, event-based cash and units, exceptions, and client read routes.
3. Pension: fund units and NAV, contribution events, future allocation draft/review, separate non-executing holding-switch drafts, current versus future holdings, projections, and exceptions.
4. Equity: plan reserve, issued versus proposed grants, tranches, vested versus released, option eligibility, exercise drafts, and release review.
5. Custody: independent opening inventory, paid versus scheduled dividends, transfer correlation and confirmation, record-date corporate-action entitlement, and a stock split that posts once.
6. Wellness: published and current education, source-backed employer rules with underlying service policy checks, benefit comparison, seminar schedule, content review, learning progress, and a bounded monthly savings calculator.
7. Portal: operator tabs for all five services and existing master/per-service access management. Automated browser smoke covers each area.

## Remaining work for a larger implementation

- Expand the fixed tenant and employee population and cover employment events, PSU certification, reserve approvals, option expiry variations, and report jobs.
- Add dedicated custody settlement and position-lot tables for all lifecycle states, plus richer reconciliation and statement generation.
- Add content revision history, distinct editorial reviewers, seminar registration and attendance, and aggregate participation reporting.
- Add operator creation forms for stock payroll and purchase cycles; those creation routes are currently API only.
- Replace the V1 summary panels with V2-derived summaries where state changes should be immediately reflected across views.
- Add managed database migrations and database-level append-only enforcement for a deployed environment. The current event guard protects SQLAlchemy ORM updates and deletes; direct SQL is outside it.
- Add delegated employee identity and end-to-end MCP/chatbot integration when the separate components are available.

The service-by-service findings, verified controls, and unresolved data-model gaps from `NMR_Realism_Research_and_QA_Pack.md` are recorded in `docs/realism-qa-review.md`.

## Validation

Backend tests, frontend build, HTTP access-control smoke, and browser navigation smoke are run locally. Browser screenshots are stored under `docs/screenshots/`. The app uses fixed test records, has no external financial execution, and should stay on localhost with its supplied local credentials.
