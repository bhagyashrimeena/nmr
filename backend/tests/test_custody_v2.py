from decimal import Decimal
import pytest

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2_models import FinancialEvent
from conftest import admin_token, auth, employee_token


PREFIX = "/api/v2/client/me/custody"


def test_custody_inventory_dividend_cash_and_scope(demo):
    client, _ = demo
    employee = auth(employee_token())
    position = client.get(PREFIX + "/positions", headers=employee).json()
    assert position["available_units"] == "120.000000" and position["cash_jpy"] == "6000.00"
    dividends = client.get(PREFIX + "/dividends", headers=employee).json()["dividends"]
    assert {x["state"] for x in dividends} == {"PAID", "SCHEDULED"}
    assert client.get(PREFIX + "/positions", headers=auth(employee_token("EMP-002"))).json()["available_units"] == "36.000000"
    assert client.get(PREFIX + "/positions", headers=auth(employee_token("SEC-001", "secondary-demo"))).json()["available_units"] == "13.000000"
    for route in ["/history", "/actions", "/transfers", "/settlements", "/statement"]:
        assert client.get(PREFIX + route, headers=employee).status_code == 200


def test_split_posted_once_after_entitlement_and_dividend_unpaid(demo):
    client, engine = demo
    admin = auth(admin_token())
    position_before = client.get(PREFIX + "/positions", headers=auth(employee_token())).json()
    action = "/api/v2/admin/tenants/toyota-demo/custody/actions/CU-SPLIT-001"
    assert client.patch(action, headers=admin, json={"state": "POSTED", "reason": "Too early"}).status_code == 409
    for state in ["ENTITLEMENT_CAPTURED", "EFFECTIVE", "POSTED", "RECONCILED"]:
        response = client.patch(action, headers=admin, json={"state": state, "reason": "Operations review"})
        assert response.status_code == 200, response.text
    assert client.patch(action, headers=admin, json={"state": "POSTED", "reason": "Duplicate"}).status_code == 409
    position_after = client.get(PREFIX + "/positions", headers=auth(employee_token())).json()
    assert Decimal(position_after["available_units"]) - Decimal(position_before["available_units"]) == 120
    assert position_after["cash_jpy"] == position_before["cash_jpy"]
    dividend = "/api/v2/admin/tenants/toyota-demo/custody/dividends/CU-DIV-SCHEDULED"
    assert client.patch(dividend, headers=admin, json={"state": "PAID", "reason": "Early payment"}).json()["error"]["code"] == "NOT_PAYABLE"
    with Session(engine) as db:
        assert len(list(db.scalars(select(FinancialEvent).where(
            FinancialEvent.source_reference == "CU-SPLIT-001")))) == 1


def test_stock_transfer_moves_exact_units_between_services(demo):
    client, _ = demo
    employee = auth(employee_token())
    admin = auth(admin_token())
    stock_before = Decimal(client.get("/api/v2/client/me/shareholding/summary", headers=employee).json()["shares_held"])
    custody_before = Decimal(client.get(PREFIX + "/positions", headers=employee).json()["available_units"])
    draft = client.post("/api/v2/client/me/shareholding/transfer-drafts",
                        headers={**auth(employee_token(scopes=["read:finance", "draft:stock"])),
                                 "Idempotency-Key": "custody-transfer-001"},
                        json={"units": "5", "recipient_account_reference": "CUST-EMP-001"}).json()
    pending = client.get(PREFIX + "/positions", headers=employee).json()
    assert pending["available_units"] == str(custody_before.quantize(Decimal("0.000001")))
    review = "/api/v2/admin/tenants/toyota-demo/shareholding/transfers/" + draft["request_id"]
    for state in ["ELIGIBILITY_CHECKED", "CORPORATE_APPROVED", "PROVIDER_FORWARDED", "COMPLETED"]:
        assert client.patch(review, headers=admin, json={"state": state, "reason": "Operations review",
                                                        "confirmation_reference": "SETTLE-EMP001-002" if state == "COMPLETED" else None}).status_code == 200
    stock_after = Decimal(client.get("/api/v2/client/me/shareholding/summary", headers=employee).json()["shares_held"])
    custody_after = Decimal(client.get(PREFIX + "/positions", headers=employee).json()["available_units"])
    assert stock_before - stock_after == custody_after - custody_before == 5
    assert client.get(PREFIX + "/settlements", headers=employee).json()["settlements"][-1]["settlement_state"] == "SETTLED_CONFIRMED"


def test_custody_switch_blocks_all_client_routes(demo):
    client, _ = demo
    employee = auth(employee_token())
    routes = ["/positions", "/history", "/dividends", "/actions", "/transfers", "/settlements", "/statement"]
    client.patch("/api/v1/admin/tenants/toyota-demo/service-access/custody",
                 headers=auth(admin_token()), json={"enabled": False, "reason": "Access review"})
    for route in routes:
        response = client.get(PREFIX + route, headers=employee)
        assert response.status_code == 403 and response.json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"
    assert client.get("/api/v2/client/me/shareholding/summary", headers=employee).status_code == 200


def test_financial_events_are_append_only(demo):
    _, engine = demo
    with Session(engine) as db:
        event = db.get(FinancialEvent, "CU-OPEN-EMP-001")
        event.quantity = Decimal("999")
        with pytest.raises(ValueError, match="append-only"):
            db.flush()
        db.rollback()
    with Session(engine) as db:
        assert db.get(FinancialEvent, "CU-OPEN-EMP-001").quantity == Decimal("120")
