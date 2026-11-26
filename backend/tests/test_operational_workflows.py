from sqlalchemy.orm import Session

from app.security import mint_token
from app.v2_models import CaseResolution, FinancialEvent, ReconciliationCase, SharePayrollBatch
from conftest import admin_token, auth, employee_token


def operator_token(tenant="toyota-demo", scopes=None):
    return mint_token(sub="operator:stock-team", role="operator", tenant_id=tenant,
                      scopes=scopes or ["ops:stock:read", "ops:stock:write"])


def test_payroll_correction_posts_cash_once_and_preserves_rejected_source(demo):
    client, engine = demo
    operator = auth(operator_token())
    detail = "/api/v2/admin/tenants/toyota-demo/shareholding/payroll-batches/PAY-EMP-002-202611"
    original = client.get(detail, headers=operator)
    assert original.status_code == 200
    assert original.json()["state"] == "REJECTED"
    assert original.json()["lines"][0]["state"] == "REJECTED"
    assert original.json()["events"] == []

    employee = auth(employee_token("EMP-002"))
    summary_route = "/api/v2/client/me/shareholding/summary"
    before = client.get(summary_route, headers=employee).json()
    route = "/api/v2/admin/tenants/toyota-demo/shareholding/cases/BREAK-STOCK-001/correct-payroll"
    body = {"evidence_reference": "PAY-REMIT-202611-002",
            "reason": "Remittance checked against signed payroll file and election"}
    assert client.post(route, headers=employee, json=body).status_code == 403
    posted = client.post(route, headers=operator, json=body)
    assert posted.status_code == 201, posted.text
    assert posted.json()["posted_cash_jpy"] == "10000.00"
    assert posted.json()["incentive_jpy"] == "500.00"
    assert posted.json()["share_units_posted"] == "0.000000"
    after = client.get(summary_route, headers=employee).json()
    assert after["shares_held"] == before["shares_held"]
    assert float(after["uninvested_cash_jpy"]) - float(before["uninvested_cash_jpy"]) == 10500
    internal = client.get("/api/v1/admin/tenants/toyota-demo/employees/EMP-002/service-summary",
                          headers=auth(admin_token())).json()
    assert internal["stock"]["operational"] == after
    assert client.get(detail, headers=operator).json()["state"] == "REJECTED"
    assert client.post(route, headers=operator, json=body).status_code == 409

    with Session(engine) as db:
        assert db.get(ReconciliationCase, "BREAK-STOCK-001").status == "RESOLVED"
        resolution = db.get(CaseResolution, "BREAK-STOCK-001")
        assert resolution.related_batch_id == "CORR-BREAK-STOCK-001"
        assert db.get(SharePayrollBatch, resolution.related_batch_id).state == "POSTED"
        events = db.query(FinancialEvent).filter_by(correlation_id="BREAK-STOCK-001").all()
        assert len(events) == 2
        assert sum(row.quantity for row in events) == 0


def test_provider_operator_is_service_and_tenant_scoped(demo):
    client, _ = demo
    operator = auth(operator_token())
    assert client.get("/api/v2/admin/tenants/toyota-demo/shareholding/operations", headers=operator).status_code == 200
    assert client.get("/api/v2/admin/tenants/toyota-demo/pension/operations", headers=operator).status_code == 403
    assert client.get("/api/v2/admin/tenants/secondary-demo/shareholding/operations", headers=operator).status_code == 403
    assert client.get("/api/v1/admin/tenants", headers=operator).status_code == 403
    read_only = auth(operator_token(scopes=["ops:stock:read"]))
    route = "/api/v2/admin/tenants/toyota-demo/shareholding/cases/BREAK-STOCK-001/correct-payroll"
    assert client.post(route, headers=read_only,
                       json={"evidence_reference": "PAY-REMIT-READ-ONLY",
                             "reason": "Attempted correction without write permission"}).status_code == 403
    assert client.get("/api/v2/admin/tenants/toyota-demo/shareholding/operations",
                      headers=auth(admin_token())).status_code == 200


def test_corporate_plan_report_is_aggregate_only(demo):
    client, _ = demo
    token = mint_token(sub="corporate:toyota-plan", role="corporate_admin",
                       tenant_id="toyota-demo", scopes=["plan:read"])
    route = "/api/v2/corporate/tenants/toyota-demo/aggregate"
    response = client.get(route, headers=auth(token))
    assert response.status_code == 200
    assert response.json()["employee_count"] == 3
    assert "EMP-001" not in response.text
    assert client.get(route.replace("toyota-demo", "secondary-demo"), headers=auth(token)).status_code == 403
    assert client.get("/api/v2/client/me/pension/account", headers=auth(token)).status_code == 403
    assert client.get("/api/v1/admin/tenants/toyota-demo/employees", headers=auth(token)).status_code == 403


def test_work_queue_case_history_and_source_derived_reports(demo):
    client, engine = demo
    admin = auth(admin_token())
    base = "/api/v2/admin/tenants/toyota-demo"
    queue = client.get(base + "/work-queue", headers=admin)
    assert queue.status_code == 200
    assert {case["service"] for case in queue.json()["cases"]} >= {"stock", "pension", "equity"}
    route = base + "/cases/BREAK-PEN-001"
    started = client.patch(route, headers=admin, json={
        "action": "INVESTIGATE", "reason": "Checking contribution enrollment against plan roster"})
    assert started.status_code == 200 and started.json()["status"] == "INVESTIGATING"
    assert started.json()["history"][-1]["to_state"] == "INVESTIGATING"
    assert client.patch(route, headers=admin, json={"action": "WAIVE", "reason": "No evidence"}).status_code == 422
    waived = client.patch(route, headers=admin, json={
        "action": "WAIVE", "reason": "Employer confirms contribution was outside this payroll period",
        "evidence_reference": "PEN-WAIVER-202610"})
    assert waived.status_code == 200 and waived.json()["status"] == "WAIVED"
    assert waived.json()["resolution"]["evidence_reference"] == "PEN-WAIVER-202610"
    assert client.patch(route, headers=admin, json={
        "action": "WAIVE", "reason": "Repeat waiver is blocked",
        "evidence_reference": "PEN-WAIVER-REPEAT"}).status_code == 409

    stock = client.get(base + "/reports/service/stock", headers=admin)
    assert stock.status_code == 200
    assert stock.json()["totals"]["journal_quantity"] == "156.000000"
    assert stock.json()["totals"]["journal_amount_jpy"] == "12000.00"
    sources = client.get(base + "/reports/service/stock/sources?limit=5&offset=0", headers=admin)
    assert sources.status_code == 200
    assert sources.json()["total"] == stock.json()["source_record_count"]
    assert len(sources.json()["items"]) == 5
    next_sources = client.get(base + "/reports/service/stock/sources?limit=5&offset=5", headers=admin)
    assert set(row["id"] for row in sources.json()["items"]).isdisjoint(
        row["id"] for row in next_sources.json()["items"])
    employee = client.get(base + "/reports/participants/EMP-001?service=stock", headers=admin)
    assert employee.status_code == 200
    assert employee.json()["journal_quantity"] == "120.000000"
    assert employee.json()["statement_references"]
    assert employee.json()["events"]
    assert client.get(base + "/reports/participants/SEC-001?service=stock",
                      headers=admin).status_code == 404
    assert client.get(base + "/reports/service/stock?as_of=2027-01-01",
                      headers=admin).status_code == 422
    with Session(engine) as db:
        assert db.get(ReconciliationCase, "BREAK-PEN-001").status == "WAIVED"
