"""Real HTTP policy smoke test. Restores every changed Toyota setting afterward."""
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
    pension_route = "/api/v1/client/me/pension"
    setting_route = "/api/v1/admin/tenants/toyota-demo/mcp-access"
    with httpx.Client(base_url=base, timeout=10) as client:
        admin_response = client.post("/api/v1/auth/admin-token", json={"username": "nmr-admin", "password": admin_password})
        admin_response.raise_for_status()
        admin = {"Authorization": f"Bearer {admin_response.json()['access_token']}"}
        employee = {"Authorization": f"Bearer {employee_token}"}
        secondary = {"Authorization": f"Bearer {secondary_token}"}
        original = client.get(setting_route, headers=admin).json()
        original_services = {row["service"]: row["enabled"] for row in original["services"]}
        def set_master(enabled, reason):
            response = client.patch(setting_route, headers=admin, json={"enabled": enabled, "reason": reason})
            response.raise_for_status()
        def set_service(service, enabled, reason):
            response = client.patch(f"/api/v1/admin/tenants/toyota-demo/service-access/{service}",
                                    headers=admin, json={"enabled": enabled, "reason": reason})
            response.raise_for_status()
        try:
            set_master(True, "HTTP smoke test setup")
            set_service("stock", True, "HTTP smoke test setup")
            set_service("pension", True, "HTTP smoke test setup")
            first = client.get(route, headers=employee)
            assert first.status_code == 200 and first.json()["shares_held"] == 120, first.text
            set_service("stock", False, "HTTP smoke test service denial")
            denied = client.get(route, headers={**employee, "X-Request-ID": "http-smoke-denied"})
            assert denied.status_code == 403 and denied.json()["error"]["code"] == "SERVICE_ACCESS_DISABLED", denied.text
            assert client.get(pension_route, headers=employee).status_code == 200
            set_service("stock", True, "HTTP smoke test service restoration")
            assert client.get(route, headers=employee).status_code == 200
            set_master(False, "HTTP smoke test master denial")
            assert client.get(route, headers=employee).json()["error"]["code"] == "MCP_ACCESS_DISABLED"
            assert client.get(pension_route, headers=employee).json()["error"]["code"] == "MCP_ACCESS_DISABLED"
            other = client.get(route, headers=secondary)
            assert other.status_code == 200 and other.json()["tenant_id"] == "secondary-demo", other.text
            set_master(True, "HTTP smoke test master restoration")
            restored = client.get(route, headers=employee)
            assert restored.status_code == 200, restored.text
            events = client.get("/api/v1/admin/audit-events?tenantId=toyota-demo", headers=admin).json()
            assert any(e["request_id"] == "http-smoke-denied" for e in events)
            print("HTTP smoke passed: stock 200 -> 403 SERVICE_ACCESS_DISABLED -> 200; pension remains 200; master OFF denies both; secondary tenant 200; denial audited")
        finally:
            for service in ("stock", "pension"):
                set_service(service, original_services[service], "Restore prior setting after HTTP smoke test")
            set_master(original["enabled"], "Restore prior setting after HTTP smoke test")


if __name__ == "__main__":
    run()
