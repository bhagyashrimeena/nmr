# Merge guide for the existing Windows `nmr wpf` project

The connected source tree at `C:\Users\bhagy\OneDrive\Desktop\nmr wpf` was not available in this chat workspace. This package is therefore a **standalone tested implementation, not a patch applied to your existing local repository**.

**Do not overwrite the existing repo blindly.** Keep its Git history, React/Vite frontend and existing tests. Use Codex in that original folder to compare these source trees and selectively transplant or port:

1. **Backend policy:** `app/main.py` — master + five independent service switches, actual per-request authorization, admin APIs and audit logging. If the original already has a security module, integrate there rather than installing a parallel policy mechanism.
2. **Seed/domain data:** `app/seed.py`, `app/domain.py` — detailed financial records, service summaries, consistent contributions/purchases/grants, and projections. Align with the original SQLAlchemy models and migrations; avoid copying into production.
3. **Frontend concepts:** `static/` — functional, restrained provider admin screens and test-API controls. The current demo uses browser-native JS to avoid npm setup. Translate views and interactions into your original React components and its design system rather than replacing its React app.
4. **API contract:** preserve current live routes if teammates already rely on them; otherwise publish a versioned mapping from `docs/API_CONTRACT.md`.
5. **Tests:** use `tests/test_provider.py` to port negative tests for *all five* per-service switches, master precedence, tenant isolation, audit and API outcomes.

When reconciling, avoid creating a second MCP server. That belongs to the teammate. The critical behavior is that every client API call checks **master AND per-service permission AND verified identity**.

## Codex merge instruction

> I have an existing NMR Workplace Finance repo in this folder and a standalone reference implementation in `nmr-workplace-finance-poc`. First inspect both projects and report any API/model conflicts. Preserve current code and UI architecture. Port the reference's domain-rich synthetic service logic, independent tenant/service permission controls, backend enforcement, access-test UI and regression tests. Maintain backwards compatibility with the teammate's API contract. Do not overwrite working features or implement a second MCP server. Run all tests and the browser smoke suite. Explicitly report what is merged, what differs, and any remaining integration gaps.
