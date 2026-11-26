from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import McpSetting
from app.v2_models import FinancialEvent, OperationAudit, SharePayrollBatch, SharePayrollLine, SharePurchaseAllocation, SharePurchaseCycle
from conftest import admin_token, auth, employee_token


def test_shareholding_ledger_reconciles_and_rejected_payroll_does_not_post(demo):
    client, engine = demo
    first = client.get("/api/v2/client/me/shareholding/summary", headers=auth(employee_token()))
    assert first.status_code == 200, first.text
    assert first.json()["shares_held"] == "120.000000"
    assert first.json()["uninvested_cash_jpy"] == "12000.00"
    assert first.json()["reconciled"] is True
    second = client.get("/api/v2/client/me/shareholding/summary", headers=auth(employee_token("EMP-002")))
    assert second.json()["shares_held"] == "36.000000"
    lines = client.get("/api/v2/client/me/shareholding/contributions?from=2026-11-01&to=2026-11-30",
                       headers=auth(employee_token("EMP-002"))).json()["contributions"]
    assert len(lines) == 1 and lines[0]["state"] == "REJECTED"
    assert lines[0]["rejection_reason"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(FinancialEvent).where(
            FinancialEvent.employee_id == "EMP-002", FinancialEvent.source_reference == "PAY-EMP-002-202611")) == 0
        assert db.get(SharePayrollBatch, "PAY-EMP-002-202611").received_jpy == Decimal("0")


def test_purchase_allocation_and_event_refs_are_consistent(demo):
    client, engine = demo
    rows = client.get("/api/v2/client/me/shareholding/purchases", headers=auth(employee_token())).json()["purchases"]
    ledger = client.get("/api/v2/client/me/shareholding/ledger", headers=auth(employee_token())).json()["events"]
    assert len(rows) == 12
    assert sum(Decimal(row["units"]) for row in rows) == Decimal("48")
    assert sum(Decimal(row["quantity"]) for row in ledger) == Decimal("120")
    with Session(engine) as db:
        for cycle in db.scalars(select(SharePurchaseCycle)):
            allocated = db.scalar(select(func.sum(SharePurchaseAllocation.units)).where(
                SharePurchaseAllocation.cycle_id == cycle.id)) or Decimal("0")
            assert allocated <= cycle.acquired_units
            assert cycle.state == "ALLOCATED"


def test_all_v2_stock_routes_share_policy_and_identity_scope(demo):
    client, _ = demo
    employee = auth(employee_token())
    routes = ["/summary", "/contributions", "/purchases", "/dividends", "/ledger"]
    prefix = "/api/v2/client/me/shareholding"
    for route in routes:
        assert client.get(prefix + route, headers=employee).status_code == 200
    admin = auth(admin_token())
    client.patch("/api/v1/admin/tenants/toyota-demo/service-access/stock", headers=admin,
                 json={"enabled": False, "reason": "Policy review"})
    for route in routes:
        denied = client.get(prefix + route, headers=employee)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"
    assert client.get("/api/v1/client/me/pension", headers=employee).status_code == 200
    client.patch("/api/v1/admin/tenants/toyota-demo/service-access/stock", headers=admin,
                 json={"enabled": True, "reason": "Policy review complete"})
    assert client.get(prefix + "/summary", headers=employee).status_code == 200


def test_transfer_draft_scope_idempotency_and_completion(demo):
    client, engine = demo
    route = "/api/v2/client/me/shareholding/transfer-drafts"
    body = {"units": "5", "recipient_account_reference": "SEC-EMP-001"}
    key = {"Idempotency-Key": "stock-transfer-001"}
    denied = client.post(route, headers={**auth(employee_token()), **key}, json=body)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    permitted = auth(employee_token(scopes=["read:finance", "draft:stock"]))
    first = client.post(route, headers={**permitted, **key}, json=body)
    assert first.status_code == 201, first.text
    request_id = first.json()["request_id"]
    assert client.post(route, headers={**permitted, **key}, json=body).json()["request_id"] == request_id
    conflict = client.post(route, headers={**permitted, **key},
                           json={"units": "6", "recipient_account_reference": "SEC-EMP-001"})
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "DUPLICATE_REQUEST"
    assert client.get(f"/api/v2/client/me/shareholding/transfers/{request_id}",
                      headers=auth(employee_token("EMP-002"))).status_code == 404
    summary = client.get("/api/v2/client/me/shareholding/summary", headers=permitted).json()
    assert summary["shares_held"] == "120.000000"
    assert summary["available_transfer_units"] == "115.000000"

    admin = auth(admin_token())
    review = f"/api/v2/admin/tenants/toyota-demo/shareholding/transfers/{request_id}"
    for state in ["ELIGIBILITY_CHECKED", "CORPORATE_APPROVED", "PROVIDER_FORWARDED", "COMPLETED"]:
        response = client.patch(review, headers=admin, json={"state": state, "reason": "Reviewed by operations"})
        assert response.status_code == 200, response.text
    assert client.patch(review, headers=admin, json={"state": "COMPLETED", "reason": "Repeated review"}).status_code == 200
    after = client.get("/api/v2/client/me/shareholding/summary", headers=permitted).json()
    assert after["shares_held"] == "115.000000"
    assert after["available_transfer_units"] == "115.000000"
    with Session(engine) as db:
        out = db.scalars(select(FinancialEvent).where(FinancialEvent.source_reference == request_id,
                                                      FinancialEvent.service == "stock")).all()
        credit = db.scalars(select(FinancialEvent).where(FinancialEvent.source_reference == request_id,
                                                         FinancialEvent.service == "custody")).all()
        assert len(out) == len(credit) == 1
        assert out[0].quantity == Decimal("-5") and credit[0].quantity == Decimal("5")
        assert out[0].correlation_id == credit[0].correlation_id
        assert db.scalar(select(func.count()).select_from(OperationAudit).where(
            OperationAudit.operation == "draft", OperationAudit.outcome == "changed")) == 1


def test_master_off_blocks_v2_and_operations_remain_admin_visible(demo):
    client, _ = demo
    admin = auth(admin_token())
    client.patch("/api/v1/admin/tenants/toyota-demo/mcp-access", headers=admin,
                 json={"enabled": False, "reason": "Policy review"})
    denied = client.get("/api/v2/client/me/shareholding/summary", headers=auth(employee_token()))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "MCP_ACCESS_DISABLED"
    operations = client.get("/api/v2/admin/tenants/toyota-demo/shareholding/operations", headers=admin)
    assert operations.status_code == 200
    assert operations.json()["exceptions"][0]["status"] == "OPEN"
    assert len(operations.json()["members"]) == 2
    assert client.get("/api/v2/admin/tenants/secondary-demo/shareholding/operations",
                      headers=admin).json()["members"][0]["employee_id"] == "SEC-001"


def test_purchase_respects_whole_share_plan_rule(demo):
    client, _ = demo
    response = client.post("/api/v2/admin/tenants/toyota-demo/shareholding/purchase-cycles",
                           headers=auth(admin_token()),
                           json={"source_reference": "FRACTIONAL-REJECT-001", "trade_date": "2026-11-26",
                                 "unit_price_jpy": "5000.00", "acquired_units": "1.5",
                                 "allocations": [{"employee_id": "EMP-001", "units": "1.5"}]})
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_PLAN_RULE"


def test_payroll_posts_cash_only_after_validation_and_duplicate_is_rejected(demo):
    client, engine = demo
    admin = auth(admin_token())
    route = "/api/v2/admin/tenants/toyota-demo/shareholding/payroll-batches"
    body = {"period": "2026-07-01", "source_reference": "PAYROLL-JUL-02",
            "expected_jpy": "10000", "lines": [{"employee_id": "EMP-002", "amount_jpy": "10000"}]}
    received = client.post(route, headers=admin, json=body)
    assert received.status_code == 201, received.text
    batch_id = received.json()["batch_id"]
    assert client.post(route, headers=admin, json=body).json()["error"]["code"] == "DUPLICATE_REQUEST"
    before = client.get("/api/v2/client/me/shareholding/summary",
                        headers=auth(employee_token("EMP-002"))).json()
    assert before["uninvested_cash_jpy"] == "0.00" and before["shares_held"] == "36.000000"
    review = route + "/" + batch_id
    assert client.patch(review, headers=admin, json={"state": "VALIDATED", "reason": "Matched to roster"}).status_code == 200
    assert client.patch(review, headers=admin, json={"state": "POSTED", "reason": "Payroll cleared"}).status_code == 200
    assert client.patch(review, headers=admin, json={"state": "POSTED", "reason": "Repeated call"}).status_code == 200
    after = client.get("/api/v2/client/me/shareholding/summary",
                       headers=auth(employee_token("EMP-002"))).json()
    assert after["uninvested_cash_jpy"] == "10000.00" and after["shares_held"] == "36.000000"
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(FinancialEvent).where(
            FinancialEvent.source_reference == "PAYROLL-JUL-02")) == 1


def test_purchase_does_not_allocate_until_settled_and_cannot_oversubscribe(demo):
    client, engine = demo
    admin = auth(admin_token())
    payroll = client.post("/api/v2/admin/tenants/toyota-demo/shareholding/payroll-batches",
                          headers=admin, json={"period": "2026-07-01", "source_reference": "PAYROLL-JUL-03",
                                               "expected_jpy": "10000",
                                               "lines": [{"employee_id": "EMP-002", "amount_jpy": "10000"}]}).json()
    payroll_route = "/api/v2/admin/tenants/toyota-demo/shareholding/payroll-batches/" + payroll["batch_id"]
    for state in ["VALIDATED", "POSTED"]:
        assert client.patch(payroll_route, headers=admin,
                            json={"state": state, "reason": "Operations review"}).status_code == 200
    route = "/api/v2/admin/tenants/toyota-demo/shareholding/purchase-cycles"
    oversubscribed = client.post(route, headers=admin,
        json={"source_reference": "PURCHASE-JUL-OVER", "trade_date": "2026-07-20",
              "unit_price_jpy": "5000", "acquired_units": "1",
              "allocations": [{"employee_id": "EMP-002", "units": "2"}]})
    assert oversubscribed.status_code == 409 and oversubscribed.json()["error"]["code"] == "RECONCILIATION_FAILED"
    created = client.post(route, headers=admin,
        json={"source_reference": "PURCHASE-JUL-02", "trade_date": "2026-07-20",
              "unit_price_jpy": "5000", "acquired_units": "1",
              "allocations": [{"employee_id": "EMP-002", "units": "1"}]})
    assert created.status_code == 201, created.text
    cycle_id = created.json()["cycle_id"]
    review = route + "/" + cycle_id
    employee = auth(employee_token("EMP-002"))
    assert client.get("/api/v2/client/me/shareholding/summary", headers=employee).json()["shares_held"] == "36.000000"
    assert client.patch(review, headers=admin, json={"state": "ALLOCATED", "reason": "Skip settlement"}).status_code == 409
    for state in ["PRICED", "SETTLED"]:
        assert client.patch(review, headers=admin, json={"state": state, "reason": "Operations review"}).status_code == 200
        assert client.get("/api/v2/client/me/shareholding/summary", headers=employee).json()["shares_held"] == "36.000000"
    assert client.patch(review, headers=admin, json={"state": "ALLOCATED", "reason": "Settlement confirmed"}).status_code == 200
    assert client.patch(review, headers=admin, json={"state": "ALLOCATED", "reason": "Repeated call"}).status_code == 200
    summary = client.get("/api/v2/client/me/shareholding/summary", headers=employee).json()
    assert summary["shares_held"] == "37.000000" and summary["uninvested_cash_jpy"] == "5000.00"
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(FinancialEvent).where(
            FinancialEvent.source_reference == "PURCHASE-JUL-02")) == 1

