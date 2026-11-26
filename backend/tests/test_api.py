from sqlalchemy.orm import Session

from app.models import AuditEvent, McpSetting
from app.security import mint_token
from conftest import admin_token, auth, employee_token


CLIENT_ROUTES = [
    "/api/v1/client/me/stock-ownership",
    "/api/v1/client/me/pension",
    "/api/v1/client/wellness/resources?topic=retirement",
    "/api/v1/client/me/custody",
    "/api/v1/client/me/equity-compensation",
]


def test_all_five_client_services_have_distinct_data(demo):
    client, _ = demo
    token = employee_token()
    responses = [client.get(route, headers=auth(token)) for route in CLIENT_ROUTES]
    assert all(r.status_code == 200 for r in responses)
    assert all(r.headers["Cache-Control"] == "no-store" for r in responses)
    assert responses[0].json()["shares_held"] == 120
    assert responses[1].json()["balance_jpy"] == 3_500_000
    assert responses[2].json()["resources"][0]["topic"] == "retirement"
    assert responses[3].json()["dividends"][0]["status"] == "credited"
    assert responses[4].json()["next_vesting"]["vest_date"] == "2027-03-01"


def test_toggle_on_off_on_persists_and_audits(demo):
    client, engine = demo
    employee = employee_token()
    admin = admin_token()
    route = CLIENT_ROUTES[0]
    assert client.get(route, headers=auth(employee)).status_code == 200
    off = client.patch("/api/v1/admin/tenants/toyota-demo/mcp-access", headers=auth(admin),
                       json={"enabled": False, "reason": "Authorization integration test"})
    assert off.status_code == 200 and off.json()["enabled"] is False
    with Session(engine) as db:
        assert db.get(McpSetting, "toyota-demo").enabled is False
    denied = client.get(route, headers={**auth(employee), "X-Request-ID": "toggle-test-denied"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "MCP_ACCESS_DISABLED"
    assert denied.json()["error"]["request_id"] == "toggle-test-denied"
    assert denied.headers["Cache-Control"] == "no-store"
    assert client.get("/api/v1/client/me/pension", headers=auth(employee)).status_code == 403
    other = client.get(route, headers=auth(employee_token("SEC-001", "secondary-demo")))
    assert other.status_code == 200 and other.json()["tenant_id"] == "secondary-demo"
    on = client.patch("/api/v1/admin/tenants/toyota-demo/mcp-access", headers=auth(admin),
                      json={"enabled": True, "reason": "Restore integration test"})
    assert on.status_code == 200 and on.json()["enabled"] is True
    assert client.get(route, headers=auth(employee)).status_code == 200
    events = client.get("/api/v1/admin/audit-events?tenantId=toyota-demo", headers=auth(admin)).json()
    assert any(e["request_id"] == "toggle-test-denied" and e["reason"] == "MCP_ACCESS_DISABLED" for e in events)
    assert any(e["outcome"] == "permitted" and e["service"] == "stock" for e in events)
    assert all("token" not in e for e in events)


def test_auth_roles_scopes_and_tenant_isolation(demo):
    client, _ = demo
    assert client.get(CLIENT_ROUTES[0]).status_code == 401
    assert client.get(CLIENT_ROUTES[0], headers=auth("nonsense")).status_code == 401
    assert client.get(CLIENT_ROUTES[0], headers=auth(employee_token(scopes=["other:scope"]))).status_code == 403
    assert client.patch("/api/v1/admin/tenants/toyota-demo/mcp-access", headers=auth(employee_token()),
                        json={"enabled": False, "reason": "Should not change"}).status_code == 403
    assert client.get("/api/v1/admin/tenants", headers=auth(employee_token())).status_code == 403
    forged_tenant = employee_token("SEC-001", "toyota-demo")
    assert client.get(CLIENT_ROUTES[0], headers=auth(forged_tenant)).status_code == 403
    invalid_sub = mint_token(sub="employee:EMP-002", role="employee", scopes=["read:finance"],
                             tenant_id="toyota-demo", employee_id="EMP-001")
    assert client.get(CLIENT_ROUTES[0], headers=auth(invalid_sub)).status_code == 403
    assert client.get(CLIENT_ROUTES[0], headers=auth(employee_token("EMP-003"))).status_code == 403
    assert client.get("/api/v1/admin/tenants/toyota-demo/employees/SEC-001/service-summary", headers=auth(admin_token())).status_code == 404


def test_admin_portal_routes_and_empty_equity(demo):
    client, _ = demo
    admin = admin_token()
    assert len(client.get("/api/v1/admin/tenants", headers=auth(admin)).json()) == 2
    assert client.get("/api/v1/admin/tenants/toyota-demo/overview", headers=auth(admin)).json()["employee_count"] == 3
    employees = client.get("/api/v1/admin/tenants/toyota-demo/employees", headers=auth(admin)).json()
    assert len(employees) == 3
    summary = client.get("/api/v1/admin/tenants/toyota-demo/employees/EMP-002/service-summary", headers=auth(admin)).json()
    assert summary["equity"]["grants"] == []
    assert summary["stock"]["shares_held"] == 36
    assert client.get("/api/v1/client/me/equity-compensation", headers=auth(employee_token("EMP-002"))).json()["grants"] == []


def test_admin_login_openapi_and_invalid_request(demo):
    client, engine = demo
    assert client.post("/api/v1/auth/admin-token", json={"username": "nmr-admin", "password": "bad"}).status_code == 401
    login = client.post("/api/v1/auth/admin-token", json={"username": "nmr-admin", "password": "test-admin-password"})
    assert login.status_code == 200 and login.json()["token_type"] == "bearer"
    spec = client.get("/openapi.json").json()
    assert all(route.split("?")[0] in spec["paths"] for route in CLIENT_ROUTES)
    assert "/api/v1/admin/tenants/{tenant_id}/mcp-access" in spec["paths"]
    invalid = client.patch("/api/v1/admin/tenants/toyota-demo/mcp-access", headers=auth(login.json()["access_token"]), json={"enabled": False, "reason": "x"})
    assert invalid.status_code == 422
    with Session(engine) as db:
        assert db.get(McpSetting, "toyota-demo").enabled is True
        assert db.query(AuditEvent).count() == 0
