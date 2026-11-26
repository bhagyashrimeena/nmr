from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.details import growth_projection, stock_summary
from app.models import AccessChange, McpSetting, TenantServiceSetting
from app.seed import seed
from conftest import admin_token, auth, employee_token


ROUTES = {
    "stock": "/api/v1/client/me/stock-ownership",
    "pension": "/api/v1/client/me/pension",
    "wellness": "/api/v1/client/wellness/resources",
    "custody": "/api/v1/client/me/custody",
    "equity": "/api/v1/client/me/equity-compensation",
}
ACCESS = "/api/v1/admin/tenants/toyota-demo/mcp-access"


def patch_service(client, service, enabled):
    return client.patch(f"/api/v1/admin/tenants/toyota-demo/service-access/{service}",
                        headers=auth(admin_token()),
                        json={"enabled": enabled, "reason": "Granular policy regression test"})


@pytest.mark.parametrize("service", list(ROUTES))
def test_each_service_roundtrip_and_independent_access(demo, service):
    client, engine = demo
    employee = auth(employee_token())
    assert client.get(ROUTES[service], headers=employee).status_code == 200
    off = patch_service(client, service, False)
    assert off.status_code == 200
    assert off.json()["effective_service_count"] == 4
    denied = client.get(ROUTES[service], headers={**employee, "X-Request-ID": f"denied-{service}"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"
    for other, route in ROUTES.items():
        if other != service:
            assert client.get(route, headers=employee).status_code == 200
    with Session(engine) as db:
        persisted = db.scalar(select(TenantServiceSetting).where(TenantServiceSetting.tenant_id == "toyota-demo",
                                                            TenantServiceSetting.service == service))
        assert persisted.enabled is False
    assert patch_service(client, service, True).status_code == 200
    assert client.get(ROUTES[service], headers=employee).status_code == 200
    changes = client.get("/api/v1/admin/tenants/toyota-demo/access-changes", headers=auth(admin_token())).json()
    assert any(c["service"] == service and c["previous_enabled"] is True and c["new_enabled"] is False for c in changes)
    events = client.get("/api/v1/admin/audit-events?tenantId=toyota-demo", headers=auth(admin_token())).json()
    assert any(e["request_id"] == f"denied-{service}" and e["reason"] == "SERVICE_ACCESS_DISABLED" for e in events)


def test_master_toggle_preserves_individual_settings_and_admin_view(demo):
    client, engine = demo
    employee = auth(employee_token())
    patch_service(client, "pension", False)
    off = client.patch(ACCESS, headers=auth(admin_token()), json={"enabled": False, "reason": "Master gate test"})
    assert off.status_code == 200
    assert off.json()["effective_service_count"] == 0
    assert next(s for s in off.json()["services"] if s["service"] == "stock")["enabled"] is True
    for route in ROUTES.values():
        denied = client.get(route, headers=employee)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "MCP_ACCESS_DISABLED"
    for route in ("/api/v1/client/me/pension/projection", "/api/v1/client/wellness/savings-projection"):
        denied = client.get(route, headers=employee)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "MCP_ACCESS_DISABLED"
    summary = client.get("/api/v1/admin/tenants/toyota-demo/employees/EMP-001/service-summary", headers=auth(admin_token()))
    assert summary.status_code == 200 and summary.json()["stock"]["shares_held"] == 120
    secondary = client.get(ROUTES["stock"], headers=auth(employee_token("SEC-001", "secondary-demo")))
    assert secondary.status_code == 200
    on = client.patch(ACCESS, headers=auth(admin_token()), json={"enabled": True, "reason": "Restore master gate"})
    assert on.json()["effective_service_count"] == 4
    assert client.get(ROUTES["stock"], headers=employee).status_code == 200
    assert client.get(ROUTES["pension"], headers=employee).json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"
    with Session(engine) as db:
        assert db.get(McpSetting, "toyota-demo").enabled is True
        assert db.scalar(select(TenantServiceSetting).where(TenantServiceSetting.tenant_id == "toyota-demo",
                                                            TenantServiceSetting.service == "pension")).enabled is False


def test_policy_write_requires_admin_and_records_previous_new(demo):
    client, engine = demo
    route = "/api/v1/admin/tenants/toyota-demo/service-access/stock"
    body = {"enabled": False, "reason": "Authorized change"}
    assert client.patch(route, headers=auth(employee_token()), json=body).status_code == 403
    assert client.patch(route, json=body).status_code == 401
    assert client.patch(route, headers=auth(admin_token()), json=body).status_code == 200
    with Session(engine) as db:
        change = db.scalars(select(AccessChange).order_by(AccessChange.id.desc())).first()
        assert change.actor == "nmr-admin" and change.tenant_id == "toyota-demo"
        assert change.service == "stock" and change.previous_enabled is True and change.new_enabled is False
        assert change.reason == "Authorized change"
        count = db.query(AccessChange).count()
    assert client.patch(route, headers=auth(admin_token()), json=body).status_code == 200
    with Session(engine) as db:
        assert db.query(AccessChange).count() == count


def test_detailed_stock_pension_custody_and_equity_reconcile(demo):
    client, engine = demo
    employee = auth(employee_token())
    stock = client.get(ROUTES["stock"], headers=employee).json()
    assert stock["shares_held"] == 120 and len(stock["recent_purchases"]) == 5
    assert stock["year_to_date_contributions_jpy"] == 220000
    assert stock["employer_incentives_jpy"] == 12000
    assert stock["uninvested_cash_jpy"] == 12000
    assert Decimal(stock["average_purchase_cost_jpy"]) == Decimal("4820.00")
    assert stock["illustrative_portfolio_value_jpy"] == 636000
    assert stock["current_quarter_purchased_shares"] == 8
    assert sum(s["shares_purchased"] for s in stock["statements"]) == 48
    assert len(stock["activity"]) == 36
    pension = client.get(ROUTES["pension"], headers=employee).json()
    assert pension["valuation_history"][0]["balance_jpy"] == pension["balance_jpy"] == 3500000
    assert pension["equity_allocation_percent"] == 80
    assert pension["illustrative_nav_change_percent"] == "4.00"
    assert pension["employer_contributions_ytd_jpy"] == 220000
    assert sum(a["percentage"] for a in pension["allocations"]) == 100
    custody = client.get(ROUTES["custody"], headers=employee).json()
    assert custody["illustrative_portfolio_value_jpy"] == 736000
    assert custody["valuation_history"][0]["illustrative_value_jpy"] == custody["illustrative_portfolio_value_jpy"]
    assert custody["pending_corporate_actions"] == 1
    assert {s["status"] for s in custody["settlements"]} == {"settled", "pending"}
    assert next(p for p in custody["positions"] if p["instrument"] == "TDEMO ordinary shares")["quantity"] == stock["shares_held"]
    equity = client.get(ROUTES["equity"], headers=employee).json()
    assert {g["award_type"] for g in equity["grants"]} == {"RSU", "Option"}
    assert equity["summary"]["exercise_eligible_options"] == 50
    assert all(g["vested_units"] + g["unvested_units"] + g["forfeited_units"] == g["granted_units"] for g in equity["grants"])
    with Session(engine) as db:
        assert stock_summary(db, "EMP-001")["dividends_received_jpy"] == custody["dividends_received_ytd_jpy"]


def test_wellness_search_progress_and_calculator_are_gated(demo):
    client, _ = demo
    employee = auth(employee_token())
    resources = client.get(ROUTES["wellness"] + "?topic=retirement&search=contribution", headers=employee).json()
    assert resources["resources"] and all(r["topic"] == "retirement" for r in resources["resources"])
    assert resources["progress"]["completed"] == 1
    assert resources["preferred_topic"] == "retirement"
    calculator = "/api/v1/client/wellness/savings-projection?monthly_jpy=10000&years=10&annual_return_pct=0"
    result = client.get(calculator, headers=employee)
    assert result.json()["projection"]["illustrative_future_value_jpy"] == 1200000
    assert client.get(calculator.replace("years=10", "years=100"), headers=employee).status_code == 422
    patch_service(client, "wellness", False)
    assert client.get(calculator, headers=employee).json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"
    admin_calculator = client.get("/api/v1/admin/tenants/toyota-demo/employees/EMP-001/wellness/savings-projection?monthly_jpy=10000&years=10&annual_return_pct=0", headers=auth(admin_token()))
    assert admin_calculator.status_code == 200


def test_pension_projection_uses_supplied_assumptions(demo):
    client, _ = demo
    employee = auth(employee_token())
    route = "/api/v1/client/me/pension/projection?years=5&annual_return_pct=0&monthly_contribution_jpy=10000"
    projection = client.get(route, headers=employee).json()["projection"]
    assert projection["illustrative_future_value_jpy"] == 3500000 + 60 * 10000
    assert projection["annual_return_pct"] == "0"
    assert growth_projection(0, 10000, 10, Decimal("0"))["illustrative_future_value_jpy"] == 1200000
    patch_service(client, "pension", False)
    assert client.get(route, headers=employee).json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"


def test_admin_can_update_synthetic_learning_progress_with_tenant_scope(demo):
    client, _ = demo
    route = "/api/v1/admin/tenants/toyota-demo/employees/EMP-001/wellness/progress/W-INV-01"
    assert client.patch(route, headers=auth(employee_token()), json={"status": "completed"}).status_code == 403
    assert client.patch(route, headers=auth(admin_token()), json={"status": "invalid"}).status_code == 422
    assert client.patch(route.replace("EMP-001", "SEC-001"), headers=auth(admin_token()), json={"status": "completed"}).status_code == 404
    updated = client.patch(route, headers=auth(admin_token()), json={"status": "completed"})
    assert updated.status_code == 200
    assert updated.json()["progress"]["completed"] == 2
    external = client.get(ROUTES["wellness"], headers=auth(employee_token())).json()
    assert next(r for r in external["resources"] if r["id"] == "W-INV-01")["progress"] == "completed"


def test_repeated_concurrent_requests_see_committed_setting(demo):
    client, _ = demo
    employee = auth(employee_token())
    patch_service(client, "stock", False)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.get(ROUTES["stock"], headers=employee).status_code, range(8)))
    assert results == [403] * 8
    patch_service(client, "stock", True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.get(ROUTES["stock"], headers=employee).status_code, range(8)))
    assert results == [200] * 8


def test_seed_extension_is_idempotent(demo):
    _, engine = demo
    with Session(engine) as db:
        before = db.query(TenantServiceSetting).count()
        seed(db)
        assert db.query(TenantServiceSetting).count() == before == 10
