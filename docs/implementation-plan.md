# NMR provider implementation plan

Scope: NMR provider application only. The Toyota chatbot and MCP adapter belong to the other developer.

## Structure

- `backend/app/models.py`: SQLite-backed synthetic tenants, employees, accounts, service settings, policy changes, and audit events.
- `backend/app/seed.py`: deterministic linked demonstration records.
- `backend/app/services.py`: original read-only service summaries, preserved for compatibility.
- `backend/app/details.py`: detailed derived service views and deterministic projection arithmetic.
- `backend/app/catalog.py`: stable service identifiers, titles, and external routes.
- `backend/app/security.py`: signed demo JWT validation, roles, tenant and employee policy checks.
- `backend/app/main.py`: versioned client and administrator routes, OpenAPI, errors, and audit logging.
- `backend/tests/`: domain and HTTP authorization tests, including ON/OFF/ON.
- `frontend/`: React administrator portal consuming the backend.
- `docs/api-contract.md`: integration contract and example MCP calls.

Implementation completed: extend seed and data model; enforce persistent master and per-service policy; enrich all five service views and calculators; upgrade portal; test independently gated services and HTTP flow; update the integration contract.

The POC uses only fictional records and offers no transaction routes. The admin portal has a separate identity and does not impersonate an employee to browse data.
