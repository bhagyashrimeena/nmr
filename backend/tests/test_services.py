from sqlalchemy.orm import Session

from app.models import CustodyPosition, PensionAccount, SharePurchase
from app.services import custody_summary, equity_summary, pension_summary, stock_summary, wellness_resources


def test_stock_and_custody_are_arithmetically_linked(demo):
    _, engine = demo
    with Session(engine) as db:
        stock = stock_summary(db, "EMP-001")
        custody = custody_summary(db, "EMP-001")
        lots = db.query(SharePurchase).filter_by(employee_id="EMP-001").all()
        position = db.query(CustodyPosition).filter_by(employee_id="EMP-001", instrument="Toyota Motor ordinary shares").one()
        assert stock["shares_held"] == position.quantity == 120
        assert stock["total_contributions_jpy"] == sum(p.amount_jpy for p in lots) == 240000
        assert all(p.amount_jpy == p.shares * p.price_jpy for p in lots)
        assert custody["dividends"][0]["status"] == "credited"


def test_pension_allocation_and_balance(demo):
    _, engine = demo
    with Session(engine) as db:
        account = db.get(PensionAccount, "EMP-001")
        pension = pension_summary(db, "EMP-001")
        assert pension["balance_jpy"] == 3_500_000
        assert pension["balance_jpy"] == account.opening_balance_jpy + pension["employee_contributions_jpy"] + pension["employer_contributions_jpy"] + pension["investment_change_jpy"]
        assert sum(a["percentage"] for a in pension["allocations"]) == 100


def test_equity_is_distinct_from_purchased_shares(demo):
    _, engine = demo
    with Session(engine) as db:
        equity = equity_summary(db, "EMP-001")
        assert equity["grants"][0]["award_type"] == "RSU"
        assert equity["grants"][0]["vested_units"] == 50
        assert equity["grants"][0]["unvested_units"] == 150
        assert equity["next_vesting"]["vest_date"].isoformat() == "2027-03-01"
        assert equity_summary(db, "EMP-002")["grants"] == []


def test_wellness_topic_filter(demo):
    _, engine = demo
    with Session(engine) as db:
        resources = wellness_resources(db, "retirement")
        assert len(resources) == 2
        assert resources[0]["topic"] == "retirement"
        assert len(wellness_resources(db)) == 8
