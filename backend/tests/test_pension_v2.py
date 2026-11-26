from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2_models import PensionFundPosition, PensionFutureAllocation
from conftest import admin_token, auth, employee_token


PREFIX = "/api/v2/client/me/pension"


def test_pension_fund_positions_match_event_balance_and_rejected_cash_is_excluded(demo):
    client, _ = demo
    employee = auth(employee_token())
    account = client.get(PREFIX + "/account", headers=employee)
    assert account.status_code == 200, account.text
    data = account.json()
    assert data["reconciled"] is True and data["balance_jpy"] == "3500000.00"
    assert sum(Decimal(row["value_jpy"]) for row in data["positions"]) == Decimal("3500000")
    assert {row["category"] for row in data["positions"]} == {"Domestic equity", "Global equity", "Bonds"}
    rejected = client.get(PREFIX + "/contributions", headers=auth(employee_token("EMP-003"))).json()["contributions"]
    assert any(row["state"] == "REJECTED" and row["source_reference"] == "PEN-REJ-001" for row in rejected)
    assert client.get(PREFIX + "/account", headers=auth(employee_token("EMP-003"))).json()["balance_jpy"] == "650000.00"


def test_future_allocation_draft_changes_no_existing_units(demo):
    client, engine = demo
    employee = auth(employee_token(scopes=["read:finance", "draft:pension"]))
    draft_route = PREFIX + "/allocation-drafts"
    body = {"allocations": [{"fund_id": "TOYOTA-DOM", "percentage": "50"},
                            {"fund_id": "TOYOTA-GLB", "percentage": "30"},
                            {"fund_id": "TOYOTA-BND", "percentage": "20"}]}
    assert client.post(draft_route, headers={**auth(employee_token()), "Idempotency-Key": "pension-draft-001"},
                       json=body).status_code == 403
    invalid = client.post(draft_route, headers={**employee, "Idempotency-Key": "pension-draft-bad"},
                          json={"allocations": [{"fund_id": "TOYOTA-DOM", "percentage": "90"}]})
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "INVALID_ALLOCATION"
    before = client.get(PREFIX + "/account", headers=employee).json()
    with Session(engine) as db:
        units_before = {row.fund_id: row.units for row in db.scalars(select(PensionFundPosition).where(
            PensionFundPosition.employee_id == "EMP-001"))}
    created = client.post(draft_route, headers={**employee, "Idempotency-Key": "pension-draft-001"}, json=body)
    assert created.status_code == 201, created.text
    instruction_id = created.json()["instruction_id"]
    assert client.post(draft_route, headers={**employee, "Idempotency-Key": "pension-draft-001"},
                       json=body).json()["instruction_id"] == instruction_id
    assert client.get(PREFIX + "/instructions/" + instruction_id,
                      headers=auth(employee_token("EMP-002"))).status_code == 404
    review = "/api/v2/admin/tenants/toyota-demo/pension/instructions/" + instruction_id
    for state in ["VALIDATED", "ACCEPTED", "EFFECTIVE_NEXT_CONTRIBUTION"]:
        response = client.patch(review, headers=auth(admin_token()), json={"state": state, "reason": "Plan review"})
        assert response.status_code == 200, response.text
    after = client.get(PREFIX + "/account", headers=employee).json()
    assert before["balance_jpy"] == after["balance_jpy"]
    with Session(engine) as db:
        units_after = {row.fund_id: row.units for row in db.scalars(select(PensionFundPosition).where(
            PensionFundPosition.employee_id == "EMP-001"))}
        future = {row.fund_id: row.percentage for row in db.scalars(select(PensionFutureAllocation).where(
            PensionFutureAllocation.employee_id == "EMP-001"))}
    assert units_before == units_after
    assert future == {"TOYOTA-DOM": Decimal("50"), "TOYOTA-GLB": Decimal("30"), "TOYOTA-BND": Decimal("20")}


def test_pension_v2_routes_obey_service_and_master_switches(demo):
    client, _ = demo
    employee = auth(employee_token())
    routes = ["/account", "/contributions", "/positions", "/funds", "/allocation", "/projections"]
    for route in routes:
        assert client.get(PREFIX + route, headers=employee).status_code == 200
    admin = auth(admin_token())
    client.patch("/api/v1/admin/tenants/toyota-demo/service-access/pension", headers=admin,
                 json={"enabled": False, "reason": "Policy review"})
    for route in routes:
        denied = client.get(PREFIX + route, headers=employee)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"
    assert client.get("/api/v2/client/me/shareholding/summary", headers=employee).status_code == 200
    operations = client.get("/api/v2/admin/tenants/toyota-demo/pension/operations", headers=admin)
    assert operations.status_code == 200 and len(operations.json()["funds"]) == 3
    client.patch("/api/v1/admin/tenants/toyota-demo/mcp-access", headers=admin,
                 json={"enabled": False, "reason": "Policy review"})
    assert client.get(PREFIX + "/account", headers=employee).json()["error"]["code"] == "MCP_ACCESS_DISABLED"

