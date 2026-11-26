from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee
from app.security import mint_token
from app.v2_models import CustodyAccountV2, TenantOperationalStatus
from conftest import admin_token, auth, employee_token


def test_transfer_requires_own_active_matching_custody_account(demo):
    client, engine = demo
    route = "/api/v2/client/me/shareholding/transfer-drafts"
    headers = {**auth(employee_token(scopes=["read:finance", "draft:stock"])),
               "Idempotency-Key": "recipient-review-001"}
    for reference in ["CUST-EMP-002", "CUST-SEC-001", "UNKNOWN-ACCOUNT"]:
        response = client.post(route, headers=headers,
                               json={"units": "5", "recipient_account_reference": reference})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "RECIPIENT_ACCOUNT_NOT_ELIGIBLE"
    with Session(engine) as db:
        db.scalar(select(CustodyAccountV2).where(CustodyAccountV2.employee_id == "EMP-001")).status = "SUSPENDED"
        db.commit()
    response = client.post(route, headers=headers,
                           json={"units": "5", "recipient_account_reference": "CUST-EMP-001"})
    assert response.status_code == 422
    with Session(engine) as db:
        db.get(CustodyAccountV2, "CUST-EMP-001").status = "ACTIVE"
        db.commit()
    assert client.post(route, headers=headers,
                       json={"units": "5", "recipient_account_reference": "CUST-EMP-001"}).status_code == 201


def test_payroll_incentive_comes_from_versioned_plan_rule(demo):
    client, _ = demo
    route = "/api/v2/admin/tenants/toyota-demo/shareholding/payroll-batches"
    body = {"period": "2026-07-01", "source_reference": "PAY-RULE-QA-001",
            "expected_jpy": "10000", "lines": [{"employee_id": "EMP-002", "amount_jpy": "10000",
                                                "incentive_jpy": "9999"}]}
    bad = client.post(route, headers=auth(admin_token()), json=body)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_PLAN_RULE"
    body["lines"][0].pop("incentive_jpy")
    accepted = client.post(route, headers=auth(admin_token()), json=body)
    assert accepted.status_code == 201
    review = route + "/" + accepted.json()["batch_id"]
    for state in ["VALIDATED", "POSTED"]:
        assert client.patch(review, headers=auth(admin_token()),
                            json={"state": state, "reason": "Rule review"}).status_code == 200
    posted = client.get("/api/v2/client/me/shareholding/contributions?from=2026-07-01&to=2026-07-31",
                        headers=auth(employee_token("EMP-002"))).json()["contributions"]
    row = next(x for x in posted if x["source_reference"] == "PAY-RULE-QA-001")
    assert row["incentive_jpy"] == "500.00"
    assert row["rule_source_reference"] == "TOYOTA-SHARE-01/RULES/2026"


def test_fractional_beneficial_interest_keeps_whole_transfer_limit(demo):
    client, _ = demo
    admin = auth(admin_token())
    route = "/api/v2/admin/tenants/toyota-demo/shareholding/purchase-cycles"
    created = client.post(route, headers=admin,
                          json={"source_reference": "FRACTIONAL-QA-001", "trade_date": "2026-11-26",
                                "unit_price_jpy": "4000", "acquired_units": "0.75",
                                "allocations": [{"employee_id": "EMP-001", "units": "0.75"}]})
    assert created.status_code == 201, created.text
    review = route + "/" + created.json()["cycle_id"]
    for state in ["PRICED", "SETTLED", "ALLOCATED"]:
        assert client.patch(review, headers=admin,
                            json={"state": state, "reason": "Purchase review"}).status_code == 200
    employee = auth(employee_token())
    summary = client.get("/api/v2/client/me/shareholding/summary", headers=employee).json()
    assert summary["shares_held"] == "120.750000"
    assert summary["available_transfer_units"] == "120.000000"
    draft = "/api/v2/client/me/shareholding/transfer-drafts"
    bad = client.post(draft, headers={**auth(employee_token(scopes=["read:finance", "draft:stock"])),
                                      "Idempotency-Key": "fractional-transfer-001"},
                      json={"units": "0.75", "recipient_account_reference": "CUST-EMP-001"})
    assert bad.status_code == 422


def test_pension_switch_draft_is_separate_from_future_allocation(demo):
    client, _ = demo
    account_route = "/api/v2/client/me/pension/account"
    before = client.get(account_route, headers=auth(employee_token())).json()
    route = "/api/v2/client/me/pension/switch-drafts"
    headers = {**auth(employee_token(scopes=["read:finance", "draft:pension"])),
               "Idempotency-Key": "switch-draft-qa-001"}
    body = {"from_fund_id": "TOYOTA-DOM", "to_fund_id": "TOYOTA-GLB", "units": "1"}
    assert client.post(route, headers=auth(employee_token()), json=body).status_code == 403
    created = client.post(route, headers=headers, json=body)
    assert created.status_code == 201 and created.json()["effect"] == "DRAFT_ONLY"
    assert client.post(route, headers=headers, json=body).json()["id"] == created.json()["id"]
    assert client.get(route + "/" + created.json()["id"],
                      headers=auth(employee_token("EMP-002"))).status_code == 404
    assert client.get(account_route, headers=auth(employee_token())).json() == before
    assert client.get("/api/v2/admin/tenants/toyota-demo/pension/operations",
                      headers=auth(admin_token())).json()["switch_drafts"][0]["state"] == "DRAFT"


def test_stock_policy_cannot_expose_custody_cash_or_stock_rules_through_wellness(demo):
    client, _ = demo
    employee = auth(employee_token())
    assert client.get("/api/v2/client/me/shareholding/dividends", headers=employee).json()["dividends"] == []
    assert client.get("/api/v1/client/me/stock-ownership", headers=employee).json()["dividends_received_jpy"] == 0
    comparison = client.get("/api/v2/client/wellness/benefit-comparison", headers=employee)
    assert comparison.status_code == 200 and len(comparison.json()["benefits"]) == 2
    no_stock = client.get("/api/v2/client/wellness/benefit-comparison",
                          headers=auth(employee_token("EMP-003")))
    assert no_stock.status_code == 403 and no_stock.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    client.patch("/api/v1/admin/tenants/toyota-demo/service-access/stock",
                 headers=auth(admin_token()), json={"enabled": False, "reason": "Privacy review"})
    denied = client.get("/api/v2/client/wellness/benefit-comparison", headers=employee)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"
    assert client.get("/api/v2/client/wellness/benefits/corporate_pension_contributions",
                      headers=employee).status_code == 200


def test_employer_and_suspended_identity_cannot_read_employee_finances(demo):
    client, engine = demo
    employer = mint_token(sub="corporate:toyota", role="employer", scopes=["read:finance", "admin:read"],
                          tenant_id="toyota-demo")
    routes = ["/api/v2/client/me/shareholding/summary", "/api/v2/client/me/pension/account",
              "/api/v2/client/me/equity/grants", "/api/v2/client/me/custody/positions"]
    for route in routes:
        assert client.get(route, headers=auth(employer)).status_code == 403
    assert client.get("/api/v2/admin/tenants/toyota-demo/pension/operations",
                      headers=auth(employer)).status_code == 403
    with Session(engine) as db:
        db.get(Employee, "EMP-001").active = False
        db.commit()
    for route in routes:
        assert client.get(route, headers=auth(employee_token())).status_code == 403


def test_inactive_tenant_blocks_new_external_calls(demo):
    client, engine = demo
    with Session(engine) as db:
        db.get(TenantOperationalStatus, "toyota-demo").status = "SUSPENDED"
        db.commit()
    denied = client.get("/api/v2/client/me/pension/account", headers=auth(employee_token()))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "TENANT_INACTIVE"
    assert client.get("/api/v2/client/me/pension/account",
                      headers=auth(employee_token("SEC-001", "secondary-demo"))).status_code == 200
