from conftest import admin_token, auth, employee_token


PREFIX = "/api/v2/client/me/equity"


def test_awards_reconcile_and_proposals_are_private(demo):
    client, _ = demo
    employee = auth(employee_token())
    grants = client.get(PREFIX + "/grants", headers=employee).json()["grants"]
    assert len(grants) == 2 and all(x["reconciled"] for x in grants)
    assert {x["id"] for x in grants} == {"G-001", "G-003"}
    assert client.get(PREFIX + "/grants/G-PROPOSED-001", headers=auth(employee_token("EMP-002"))).status_code == 404
    assert client.get(PREFIX + "/grants/G-002", headers=employee).status_code == 404
    options = client.get(PREFIX + "/options", headers=employee).json()["options"]
    assert options[0]["currently_exercisable_units"] == 50


def test_exercise_draft_is_scoped_idempotent_and_has_no_execution(demo):
    client, _ = demo
    route = PREFIX + "/exercise-drafts"
    body = {"grant_id": "G-003", "units": 20}
    key = {"Idempotency-Key": "exercise-001"}
    assert client.post(route, headers={**auth(employee_token()), **key}, json=body).status_code == 403
    allowed = auth(employee_token(scopes=["read:finance", "draft:equity"]))
    assert client.post(route, headers={**allowed, **key}, json={**body, "units": 51}).status_code == 422
    created = client.post(route, headers={**allowed, **key}, json=body)
    assert created.status_code == 201 and created.json()["effect"] == "DRAFT_ONLY"
    assert client.post(route, headers={**allowed, **key}, json=body).json()["id"] == created.json()["id"]
    assert client.post(route, headers={**allowed, **key}, json={**body, "units": 21}).status_code == 409
    assert client.get(PREFIX + "/options", headers=allowed).json()["options"][0]["currently_exercisable_units"] == 50


def test_release_states_separate_from_custody_and_grant_reserve(demo):
    client, _ = demo
    admin = auth(admin_token())
    route = "/api/v2/admin/tenants/toyota-demo/equity/releases/REL-G-001"
    before = client.get(PREFIX + "/grants/G-001", headers=auth(employee_token())).json()
    assert before["vested_unreleased_units"] == 50
    for state in ["VERIFIED", "APPROVED", "SIMULATED_RELEASED"]:
        result = client.patch(route, headers=admin, json={"state": state, "reason": "Award review"})
        assert result.status_code == 200, result.text
    after = client.get(PREFIX + "/grants/G-001", headers=auth(employee_token())).json()
    assert after["vested_unreleased_units"] == 30 and after["released_units"] == 20
    assert after["reconciled"] is True
    assert client.patch(route, headers=admin, json={"state": "SIMULATED_RELEASED", "reason": "Again"}).status_code == 409
    operations = client.get("/api/v2/admin/tenants/toyota-demo/equity/operations", headers=admin).json()
    assert operations["plan"]["issued_units"] == 400
    assert operations["plan"]["remaining_units"] == 9600
    proposed = "/api/v2/admin/tenants/toyota-demo/equity/grants/G-PROPOSED-001"
    for state in ["APPROVED", "ISSUED", "ACTIVE"]:
        assert client.patch(proposed, headers=admin, json={"state": state, "reason": "Grant review"}).status_code == 200
    assert client.get(PREFIX + "/grants", headers=auth(employee_token("EMP-002"))).json()["grants"][0]["id"] == "G-PROPOSED-001"


def test_equity_switch_gates_every_client_route(demo):
    client, _ = demo
    employee = auth(employee_token())
    routes = ["/grants", "/grants/G-001", "/vesting", "/options", "/releases", "/statement"]
    for route in routes:
        assert client.get(PREFIX + route, headers=employee).status_code == 200
    client.patch("/api/v1/admin/tenants/toyota-demo/service-access/equity",
                 headers=auth(admin_token()), json={"enabled": False, "reason": "Review"})
    for route in routes:
        denied = client.get(PREFIX + route, headers=employee)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "SERVICE_ACCESS_DISABLED"
    assert client.get("/api/v2/client/me/pension/account", headers=employee).status_code == 200
