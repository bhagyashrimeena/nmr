# NMR provider implementation plan

Scope: NMR provider application only. The Toyota chatbot and MCP adapter belong to the other developer.

## Structure

- `backend/app/models.py`: SQLite-backed synthetic tenants, employees, accounts, activity, and audit events.
- `backend/app/seed.py`: deterministic linked demonstration records.
- `backend/app/services.py`: five read-only service summaries.
- `backend/app/security.py`: signed demo JWT validation, roles, tenant and employee policy checks.
- `backend/app/main.py`: versioned client and administrator routes, OpenAPI, errors, and audit logging.
- `backend/tests/`: domain and HTTP authorization tests, including ON/OFF/ON.
- `frontend/`: React administrator portal consuming the backend.
- `docs/api-contract.md`: handoff contract and example calls for the MCP developer.

Implementation order: data and service functions; authenticated API and policy; admin portal; tests; local HTTP smoke test and handoff docs.

The POC uses only fictional records and offers no transaction routes. The admin portal has a separate identity and does not impersonate an employee to browse data.
