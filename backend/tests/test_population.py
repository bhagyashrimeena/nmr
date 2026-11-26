from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import Base, make_engine
from app.models import Employee, Tenant
from app.population_seed import seed_population, seed_service_agreements
from app.seed import seed
from app.stock_v2 import stock_summary
from app.v2_models import ClientServiceAgreement, ParticipantOperationalProfile
from app.v2_seed import seed_v2
from app.v2_pension_seed import seed_pension
from app.v2_equity_seed import seed_equity
from app.v2_custody_seed import seed_custody
from app.v2_wellness_seed import seed_wellness


def test_population_is_deterministic_and_has_linked_records(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'population.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed(db)
        seed_population(db)
        seed_v2(db)
        seed_service_agreements(db)
        seed_pension(db)
        seed_equity(db)
        seed_custody(db)
        seed_wellness(db)
        assert db.scalar(select(func.count()).select_from(Tenant)) == 3
        assert db.scalar(select(func.count()).select_from(Employee)) == 256
        assert db.scalar(select(func.count()).select_from(ClientServiceAgreement)) == 15
        assert db.get(ParticipantOperationalProfile, "TYO-0011").cohort == "RECENT_JOINER"
        assert not db.get(Employee, "AST-0017").active
        assert stock_summary(db, "toyota-demo", "TYO-0001")["uninvested_cash_jpy"] == "3000.00"
        assert stock_summary(db, "asterfield", "AST-0001")["shares_held"] == "24.000000"
        seed_population(db)
        seed_service_agreements(db)
        assert db.scalar(select(func.count()).select_from(Employee)) == 256
        assert db.scalar(select(func.count()).select_from(ClientServiceAgreement)) == 15
    engine.dispose()
