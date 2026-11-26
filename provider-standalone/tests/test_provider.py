"""Real authorization and financial-invariant tests on an isolated seeded SQLite DB."""
import os, tempfile
os.environ["NMR_DATABASE_URL"]="sqlite:///"+tempfile.gettempdir()+"/nmr_provider_pytest.sqlite3"
os.environ["NMR_DEMO_MODE"]="true"
os.environ["NMR_JWT_SECRET"]="test-secret-use-only-in-tests-32bytes-minimum"
from fastapi.testclient import TestClient
from app.main import app
from app.seed import seed_database, SERVICES
from app.security import issue_demo_token
from app.database import SessionLocal
from app.models import AuditEvent
from sqlalchemy import select
import jwt
import pytest

@pytest.fixture(autouse=True)
def fresh_db():
    seed_database(reset=True)

@pytest.fixture
def client():
    with TestClient(app) as c: yield c

def auth(persona):
    return {"Authorization":"Bearer "+issue_demo_token(persona)}

def admin_patch(client,path,enabled):
    return client.patch(path,json={"enabled":enabled,"reason":"Policy regression test"},headers=auth("admin"))

ROUTES={
 "stock-ownership":"/api/v1/client/me/stock-ownership",
 "pension":"/api/v1/client/me/pension",
 "wellness":"/api/v1/client/wellness/resources",
 "custody":"/api/v1/client/me/custody",
 "equity-compensation":"/api/v1/client/me/equity-compensation"
}

def test_health_and_openapi(client):
    assert client.get('/health').json()['status']=='ok'
    assert client.get('/openapi.json').status_code==200
    assert client.get('/').status_code==200

def test_admin_and_full_service_catalog(client):
    r=client.get('/api/v1/admin/tenants/toyota-demo/mcp-access',headers=auth('admin'))
    assert r.status_code==200
    assert set(x['key'] for x in r.json()['services'])==set(SERVICES)
    assert len(client.get('/api/v1/admin/tenants/toyota-demo/employees',headers=auth('admin')).json())==3

def test_every_external_service_returns_detailed_data(client):
    for key,route in ROUTES.items():
        r=client.get(route,headers=auth('toyota-001'))
        assert r.status_code==200,(key,r.text)
        assert r.json()['service']==key
        assert r.headers['Cache-Control']=='no-store, private'
        assert r.headers['X-Request-ID']
        assert len(r.json().keys())>=4

def test_individual_service_toggle_is_backend_enforced(client):
    for key,route in ROUTES.items():
        assert client.get(route,headers=auth('toyota-001')).status_code==200
        p=admin_patch(client,f'/api/v1/admin/tenants/toyota-demo/service-access/{key}',False)
        assert p.status_code==200,p.text
        forbidden=client.get(route,headers=auth('toyota-001'))
        assert forbidden.status_code==403
        assert forbidden.json()['error']['code']=='SERVICE_ACCESS_DISABLED'
        for other,other_route in ROUTES.items():
            if other!=key: assert client.get(other_route,headers=auth('toyota-001')).status_code==200
        assert admin_patch(client,f'/api/v1/admin/tenants/toyota-demo/service-access/{key}',True).status_code==200
        assert client.get(route,headers=auth('toyota-001')).status_code==200

def test_master_toggle_preserves_service_settings(client):
    admin_patch(client,'/api/v1/admin/tenants/toyota-demo/service-access/pension',False)
    assert admin_patch(client,'/api/v1/admin/tenants/toyota-demo/mcp-access',False).status_code==200
    for route in ROUTES.values():
        r=client.get(route,headers=auth('toyota-001'))
        assert r.status_code==403 and r.json()['error']['code']=='MCP_ACCESS_DISABLED'
    assert client.get(ROUTES['stock-ownership'],headers=auth('harbor-001')).status_code==200
    assert admin_patch(client,'/api/v1/admin/tenants/toyota-demo/mcp-access',True).status_code==200
    assert client.get(ROUTES['stock-ownership'],headers=auth('toyota-001')).status_code==200
    r=client.get(ROUTES['pension'],headers=auth('toyota-001'))
    assert r.status_code==403 and r.json()['error']['code']=='SERVICE_ACCESS_DISABLED'

def test_admin_can_still_browse_while_external_access_off(client):
    admin_patch(client,'/api/v1/admin/tenants/toyota-demo/mcp-access',False)
    r=client.get('/api/v1/admin/tenants/toyota-demo/employees/TYO-001/services/stock-ownership',headers=auth('admin'))
    assert r.status_code==200 and r.json()['enrolled']

def test_employees_cannot_change_permissions_or_browse_admin(client):
    r=admin_patch_with_headers(client,'/api/v1/admin/tenants/toyota-demo/mcp-access',False,auth('toyota-001'))
    assert r.status_code==403
    assert r.json()['error']['code']=='INSUFFICIENT_PERMISSIONS'
    assert client.get('/api/v1/admin/tenants',headers=auth('toyota-001')).status_code==403

def admin_patch_with_headers(client,path,enabled,headers):
    return client.patch(path,json={'enabled':enabled,'reason':'Unauthorized test attempt'},headers=headers)

def test_missing_and_bad_tokens(client):
    assert client.get(ROUTES['pension']).status_code==401
    assert client.get(ROUTES['pension'],headers={'Authorization':'Bearer garbage'}).status_code==401
    bad=jwt.encode({'iss':'nmr-workplace-demo','aud':'nmr-provider-api','sub':'attacker','role':'admin'},'wrong-key-long-enough-for-hmac-sha256-tests',algorithm='HS256')
    assert client.get('/api/v1/admin/tenants',headers={'Authorization':'Bearer '+bad}).status_code==401

def test_tenant_and_employee_boundaries(client):
    toyota=client.get(ROUTES['stock-ownership'],headers=auth('toyota-001')).json()
    harbor=client.get(ROUTES['stock-ownership'],headers=auth('harbor-001')).json()
    assert toyota['employee_id']=='TYO-001' and harbor['employee_id']=='HBR-001'
    assert toyota['summary']['shares_held']!=harbor['summary']['shares_held']
    fake_client=client.get(ROUTES['stock-ownership']+'?employee_id=HBR-001&tenant_id=harbor-demo',headers=auth('toyota-001'))
    assert fake_client.json()['employee_id']=='TYO-001'
    assert client.get('/api/v1/admin/tenants/toyota-demo/employees/HBR-001/services/stock-ownership',headers=auth('admin')).status_code==404

def test_stock_and_pension_reconciliation(client):
    s=client.get(ROUTES['stock-ownership'],headers=auth('toyota-001')).json()
    assert sum(x['shares'] for x in s['purchases'])==s['summary']['shares_held']
    assert sum(x['amount_jpy'] for x in s['purchases'])==s['summary']['total_purchases_jpy']
    assert s['summary']['employee_contributions_jpy']+s['summary']['employer_incentives_jpy']-s['summary']['total_purchases_jpy']==s['summary']['uninvested_cash_jpy']
    p=client.get(ROUTES['pension'],headers=auth('toyota-001')).json()
    assert sum(a['percent'] for a in p['allocations'])==100
    a=p['account']
    assert a['opening_balance_jpy']+p['summary']['total_contributions_2026_jpy']+a['investment_change_jpy']==a['current_balance_jpy']

def test_equity_grants_reconcile_and_unenrolled(client):
    e=client.get(ROUTES['equity-compensation'],headers=auth('toyota-001')).json()
    for g in e['grants']:
        assert g['units_vested']+g['units_unvested']+g['units_forfeited']==g['units_granted']
    assert client.get(ROUTES['equity-compensation'],headers=auth('toyota-003')).json()['enrolled'] is False

def test_disabled_service_returns_denial_audit_event(client):
    admin_patch(client,'/api/v1/admin/tenants/toyota-demo/service-access/custody',False)
    client.get(ROUTES['custody'],headers=auth('toyota-001'))
    rows=client.get('/api/v1/admin/audit-events?tenant_id=toyota-demo',headers=auth('admin')).json()
    assert any(a['service_key']=='custody' and a['outcome']=='DENIED' and a['reason']=='SERVICE_ACCESS_DISABLED' for a in rows)
    assert any(a['action']=='SERVICE_ACCESS_CHANGED' for a in rows)

def test_projection_bounds_and_wellness_topic_filter(client):
    assert client.get(ROUTES['pension']+'?years=100',headers=auth('toyota-001')).status_code==422
    r=client.get(ROUTES['wellness']+'?topic=Retirement',headers=auth('toyota-001')).json()
    assert len(r['resources'])>=1 and all(x['topic']=='Retirement' for x in r['resources'])

def test_access_state_persists_between_sessions(client):
    admin_patch(client,'/api/v1/admin/tenants/toyota-demo/service-access/wellness',False)
    # Independent DB session simulates server-side persistent policy (not UI state)
    with SessionLocal() as db:
        from app.models import ServicePermission
        row=db.scalar(select(ServicePermission).where(ServicePermission.tenant_id=='toyota-demo',ServicePermission.service_key=='wellness'))
        assert row.enabled is False

def test_wellness_calculator_is_deterministic_and_gated(client):
    path='/api/v1/client/wellness/savings-projection?monthly_jpy=10000&years=10&annual_return_pct=0'
    r=client.get(path,headers=auth('toyota-001'))
    assert r.status_code==200
    data=r.json()
    assert data['illustrative_future_value_jpy']==1200000
    assert data['total_contributions_jpy']==1200000
    admin_patch(client,'/api/v1/admin/tenants/toyota-demo/service-access/wellness',False)
    r=client.get(path,headers=auth('toyota-001'))
    assert r.status_code==403 and r.json()['error']['code']=='SERVICE_ACCESS_DISABLED'
