"""Regression checks: V2 admin participant views use the authoritative financial records."""
from decimal import Decimal

from conftest import admin_token, auth, employee_token


BASE = "/api/v2/admin/tenants/toyota-demo/employees"


def get_record(client, employee_id, service, headers=None):
    return client.get(BASE + "/" + employee_id + "/source-record/" + service,
                      headers=headers or auth(admin_token()))


def test_authoritative_records_match_employee_api(demo):
    client, _ = demo
    stock = get_record(client, "EMP-001", "stock")
    assert stock.status_code == 200, stock.text
    body = stock.json()
    assert body["source_version"] == "V2_LEDGER"
    employee_stock = client.get("/api/v2/client/me/shareholding/summary",
                                headers=auth(employee_token())).json()
    assert body["summary"]["shares_held"] == employee_stock["shares_held"]
    assert body["summary"]["uninvested_cash_jpy"] == employee_stock["uninvested_cash_jpy"]
    assert body["journal"]
    assert all(row["source_reference"] for row in body["journal"])

    pension = get_record(client, "EMP-001", "pension")
    assert pension.status_code == 200, pension.text
    employee_pension = client.get("/api/v2/client/me/pension/account",
                                  headers=auth(employee_token())).json()
    assert pension.json()["summary"]["balance_jpy"] == employee_pension["balance_jpy"]
    assert pension.json()["summary"]["reconciled"] is True

    custody = get_record(client, "EMP-001", "custody")
    assert custody.status_code == 200, custody.text
    employee_custody = client.get("/api/v2/client/me/custody/positions",
                                  headers=auth(employee_token())).json()
    assert custody.json()["summary"]["available_units"] == employee_custody["available_units"]

    equity = get_record(client, "EMP-001", "equity")
    assert equity.status_code == 200, equity.text
    assert all(item["reconciled"] for item in equity.json()["details"])


def test_admin_source_changes_after_evidenced_payroll_correction(demo):
    client, _ = demo
    before = get_record(client, "EMP-002", "stock").json()
    before_cash = Decimal(before["summary"]["uninvested_cash_jpy"])
    before_shares = before["summary"]["shares_held"]

    response = client.post(
        "/api/v2/admin/tenants/toyota-demo/shareholding/cases/BREAK-STOCK-001/correct-payroll",
        headers=auth(admin_token()),
        json={
            "evidence_reference": "PAY-V2-SOURCE-202611",
            "reason": "Matched remittance against verified payroll election and employer source file",
        },
    )
    assert response.status_code == 201, response.text

    after = get_record(client, "EMP-002", "stock").json()
    assert after["summary"]["shares_held"] == before_shares
    assert Decimal(after["summary"]["uninvested_cash_jpy"]) - before_cash == Decimal("10500.00")
    assert any(row["source_reference"] == "PAY-V2-SOURCE-202611" for row in after["journal"])
    employee = client.get("/api/v2/client/me/shareholding/summary",
                          headers=auth(employee_token("EMP-002"))).json()
    assert employee["uninvested_cash_jpy"] == after["summary"]["uninvested_cash_jpy"]


def test_source_record_enforces_provider_admin_role_and_tenant_isolation(demo):
    client, _ = demo
    assert get_record(client, "EMP-001", "stock", auth(employee_token())).status_code == 403
    assert get_record(client, "SEC-001", "stock").status_code == 404
    assert get_record(client, "EMP-001", "not-a-service").status_code == 404
    assert get_record(client, "EMP-002", "stock").status_code == 200
    # An internal administrator retains its provider-only view even when the
    # externally exposed stock tool is disabled for the corporate tenant.
    control = "/api/v1/admin/tenants/toyota-demo/service-access/stock"
    assert client.patch(control, headers=auth(admin_token()),
                        json={"enabled": False, "reason": "Provider source control test"}).status_code == 200
    assert get_record(client, "EMP-001", "stock").status_code == 200
    assert client.get("/api/v2/client/me/shareholding/summary",
                      headers=auth(employee_token())).status_code == 403
