import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Base, get_db, make_engine
from app.main import app
from app.seed import seed
from app.v2_seed import seed_v2
from app.v2_pension_seed import seed_pension
from app.v2_equity_seed import seed_equity
from app.v2_custody_seed import seed_custody
from app.v2_wellness_seed import seed_wellness
from app.security import mint_token


@pytest.fixture
def demo(tmp_path, monkeypatch):
    monkeypatch.setenv("NMR_JWT_SECRET", "test-secret-with-at-least-thirty-two-chars")
    monkeypatch.setenv("NMR_ADMIN_PASSWORD", "test-admin-password")
    engine = make_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed(db)
        seed_v2(db)
        seed_pension(db)
        seed_equity(db)
        seed_custody(db)
        seed_wellness(db)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def employee_token(employee_id="EMP-001", tenant_id="toyota-demo", scopes=None):
    return mint_token(sub=f"employee:{employee_id}", role="employee", scopes=scopes or ["read:finance"],
                      tenant_id=tenant_id, employee_id=employee_id)


def admin_token():
    return mint_token(sub="nmr-admin", role="admin", scopes=["admin:read", "admin:write"])


def auth(token):
    return {"Authorization": f"Bearer {token}"}
