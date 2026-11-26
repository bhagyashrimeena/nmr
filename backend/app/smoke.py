"""Real HTTP smoke test against a running local backend. Restores Toyota's initial access setting."""
import os

import httpx

from .security import mint_token


def run():
    base = os.getenv("NMR_API_BASE", "http://127.0.0.1:8000")
    admin_password = os.environ["NMR_ADMIN_PASSWORD"]
    employee_token = mint_token(sub="employee:EMP-001", role="employee", scopes=["read:finance"],
                                tenant_id="toyota-demo", employee_id="EMP-001")
    secondary_token = mint_token(sub="employee:SEC-001", role="employee", scopes=["read:finance"],
                                 tenant_id="secondary-demo", employee_id="SEC-001")
    route = "/api/v1/client/me/stock-ownership"
    setting_route = "/api/v1/admin/tenants/toyota-demo/mcp-access"
    with httpx.Client(base_url=base, timeout=10) as client:
        admin_response = client.post("/api/v1/auth/admin-token", json={"username": "nmr-admin", "password": admin_password})
        admin_response.raise_for_status()
        admin = {"Authorization": f"Bearer {admin_response.json()['access_token']}"}
        employee = {"Authorization": f"Bearer {employee_token}"}
        secondary = {"Authorization": f"Bearer {secondary_token}"}
        original = client.get(setting_route, headers=admin).json()["enabled"]
        try:
            client.patch(setting_route, headers=admin, json={"enabled": True, "reason": "HTTP smoke test setup"}).raise_for_status()
            first = client.get(route, headers=employee)
            assert first.status_code == 200 and first.json()["shares_held"] == 120, first.text
            client.patch(setting_route, headers=admin, json={"enabled": False, "reason": "HTTP smoke test denial"}).raise_for_status()
            denied = client.get(route, headers={**employee, "X-Request-ID": "http-smoke-denied"})
            assert denied.status_code == 403 and denied.json()["error"]["code"] == "MCP_ACCESS_DISABLED", denied.text
            other = client.get(route, headers=secondary)
            assert other.status_code == 200 and other.json()["tenant_id"] == "secondary-demo", other.text
            client.patch(setting_route, headers=admin, json={"enabled": True, "reason": "HTTP smoke test restoration"}).raise_for_status()
            restored = client.get(route, headers=employee)
            assert restored.status_code == 200, restored.text
            events = client.get("/api/v1/admin/audit-events?tenantId=toyota-demo", headers=admin).json()
            assert any(e["request_id"] == "http-smoke-denied" for e in events)
            print("HTTP smoke passed: 200 -> 403 MCP_ACCESS_DISABLED -> 200; secondary tenant 200; denial audited")
        finally:
            client.patch(setting_route, headers=admin, json={"enabled": original, "reason": "Restore prior setting after HTTP smoke test"}).raise_for_status()


if __name__ == "__main__":
    run()
