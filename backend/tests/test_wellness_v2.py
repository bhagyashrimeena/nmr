from conftest import admin_token, auth, employee_token


PREFIX = "/api/v2/client/wellness"


def test_only_current_published_tenant_content_is_exposed(demo):
    client, _ = demo
    toyota = client.get(PREFIX + "/education", headers=auth(employee_token())).json()["items"]
    assert {x["id"] for x in toyota} == {"ED-RET-01", "ED-EQ-01"}
    sakura = client.get(PREFIX + "/education", headers=auth(employee_token("SEC-001", "secondary-demo"))).json()["items"]
    assert {x["id"] for x in sakura} == {"ED-SAK-01"}
    filtered = client.get(PREFIX + "/education?category=equity", headers=auth(employee_token())).json()["items"]
    assert [x["id"] for x in filtered] == ["ED-EQ-01"]


def test_benefit_rule_must_be_current_and_tenant_specific(demo):
    client, _ = demo
    rule = client.get(PREFIX + "/benefits/shareholding_incentive", headers=auth(employee_token()))
    assert rule.status_code == 200 and rule.json()["source_reference"] == "TOYOTA-SHARE-01/RULES/2026"
    absent = client.get(PREFIX + "/benefits/shareholding_incentive",
                        headers=auth(employee_token("SEC-001", "secondary-demo")))
    assert absent.status_code == 404 and absent.json()["error"]["code"] == "BENEFIT_RULE_NOT_AVAILABLE"


def test_calculator_reproducible_and_policy_gated(demo):
    client, _ = demo
    employee = auth(employee_token())
    path = PREFIX + "/calculators/monthly-savings?monthly_jpy=10000&months=12&annual_rate_percent=0"
    response = client.get(path, headers=employee)
    assert response.status_code == 200
    assert response.json()["contributed_jpy"] == "120000.00"
    assert response.json()["future_value_jpy"] == "120000.00"
    assert client.get(path, headers=employee).json() == response.json()
    assert client.get(PREFIX + "/progress", headers=employee).status_code == 200
    assert client.get(PREFIX + "/seminars", headers=employee).status_code == 200
    client.patch("/api/v1/admin/tenants/toyota-demo/service-access/wellness",
                 headers=auth(admin_token()), json={"enabled": False, "reason": "Review"})
    for route in ["/education", "/benefits/shareholding_incentive", "/progress", "/seminars",
                  "/calculators/monthly-savings"]:
        denied = client.get(PREFIX + route, headers=employee)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"


def test_content_review_lifecycle(demo):
    client, _ = demo
    admin = auth(admin_token())
    route = "/api/v2/admin/tenants/toyota-demo/wellness/content/ED-DRAFT-01"
    for state in ["IN_REVIEW", "APPROVED", "PUBLISHED"]:
        response = client.patch(route, headers=admin, json={"state": state, "reason": "Editorial review"})
        assert response.status_code == 200, response.text
    items = client.get(PREFIX + "/education", headers=auth(employee_token())).json()["items"]
    assert "ED-DRAFT-01" in {x["id"] for x in items}
    assert client.patch(route, headers=admin, json={"state": "PUBLISHED", "reason": "Again"}).status_code == 409
    assert client.get("/api/v2/admin/tenants/secondary-demo/wellness/operations", headers=admin).json()["benefit_rules"] == []
