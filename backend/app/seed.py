"""Deterministic fictional records; safe to call repeatedly on an existing demo DB."""
from datetime import date

from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import (CorporateAction, CustodyPosition, Dividend, Employee, EquityGrant,
                     McpSetting, PayrollContribution, PensionAccount, PensionAllocation,
                     PensionContribution, SharePurchase, StockAccount, Tenant,
                     VestingEvent, WellnessResource)

AS_OF = date(2026, 11, 25)


def seed(db):
    if db.scalar(select(Tenant.id).limit(1)):
        return
    db.add_all([
        Tenant(id="toyota-demo", name="Toyota · hypothetical client"),
        Tenant(id="secondary-demo", name="Sakura Mobility · fictional client"),
        McpSetting(tenant_id="toyota-demo", enabled=True, changed_by="seed", reason="Initial demo setting"),
        McpSetting(tenant_id="secondary-demo", enabled=True, changed_by="seed", reason="Initial demo setting"),
        Employee(id="EMP-001", tenant_id="toyota-demo", display_name="Aiko Mori", allowed_services="stock,pension,wellness,custody,equity"),
        Employee(id="EMP-002", tenant_id="toyota-demo", display_name="Kenji Sato", allowed_services="stock,pension,wellness,custody,equity"),
        Employee(id="EMP-003", tenant_id="toyota-demo", display_name="Yui Tanaka", allowed_services="pension,wellness,equity"),
        Employee(id="SEC-001", tenant_id="secondary-demo", display_name="Hana Kato", allowed_services="stock,pension,wellness,custody,equity"),
        StockAccount(employee_id="EMP-001", plan_id="TDEMO-SHARE-01", opening_shares=72, monthly_contribution_jpy=20000),
        StockAccount(employee_id="EMP-002", plan_id="TDEMO-SHARE-01", opening_shares=30, monthly_contribution_jpy=10000),
        StockAccount(employee_id="SEC-001", plan_id="SDEMO-SHARE-01", opening_shares=10, monthly_contribution_jpy=12000),
        PensionAccount(employee_id="EMP-001", account_type="Corporate defined contribution", opening_balance_jpy=3000000, investment_change_jpy=80000),
        PensionAccount(employee_id="EMP-002", account_type="Corporate defined contribution", opening_balance_jpy=1800000, investment_change_jpy=25000),
        PensionAccount(employee_id="EMP-003", account_type="Corporate defined contribution", opening_balance_jpy=640000, investment_change_jpy=-8000),
        PensionAccount(employee_id="SEC-001", account_type="Corporate defined contribution", opening_balance_jpy=920000, investment_change_jpy=14000),
        WellnessResource(id="W-RET-01", title="Share plans and retirement saving", topic="retirement", description="How payroll share purchases differ from pension contributions.", content="A shareholding plan buys company shares with employee contributions. A corporate pension invests for retirement under its plan rules. Both involve risk; neither is a guaranteed return."),
        WellnessResource(id="W-BUD-01", title="Building an emergency buffer", topic="budgeting", description="A plain-language guide to setting aside short-term cash.", content="Review regular spending and choose a savings target that fits your circumstances. This educational guide is not personal financial advice."),
        WellnessResource(id="W-EQ-01", title="Understanding restricted stock units", topic="equity", description="Grant, vesting, and holding are different events.", content="An RSU award is distinct from shares purchased through payroll. Vesting schedules and tax treatment depend on plan terms. Consult the plan documents for details."),
        CustodyPosition(employee_id="EMP-001", instrument="TDEMO ordinary shares", quantity=120),
        CustodyPosition(employee_id="EMP-002", instrument="TDEMO ordinary shares", quantity=36),
        CustodyPosition(employee_id="SEC-001", instrument="SDEMO ordinary shares", quantity=13),
        Dividend(employee_id="EMP-001", payment_date=date(2026, 9, 30), instrument="TDEMO ordinary shares", amount_jpy=6000, status="credited"),
        Dividend(employee_id="EMP-002", payment_date=date(2026, 9, 30), instrument="TDEMO ordinary shares", amount_jpy=1800, status="credited"),
        Dividend(employee_id="SEC-001", payment_date=date(2026, 9, 30), instrument="SDEMO ordinary shares", amount_jpy=520, status="credited"),
        CorporateAction(id="CA-01", instrument="TDEMO ordinary shares", title="Annual dividend record date notice", effective_date=date(2026, 9, 1)),
        CorporateAction(id="CA-02", instrument="SDEMO ordinary shares", title="Annual dividend record date notice", effective_date=date(2026, 9, 1)),
        EquityGrant(id="G-001", employee_id="EMP-001", award_type="RSU", granted_units=200, grant_date=date(2025, 4, 1)),
        EquityGrant(id="G-002", employee_id="EMP-003", award_type="Option", granted_units=100, grant_date=date(2026, 1, 1)),
        VestingEvent(grant_id="G-001", vest_date=date(2026, 4, 1), units=50, status="vested"),
        VestingEvent(grant_id="G-001", vest_date=date(2027, 4, 1), units=50, status="scheduled"),
        VestingEvent(grant_id="G-001", vest_date=date(2028, 4, 1), units=50, status="scheduled"),
        VestingEvent(grant_id="G-001", vest_date=date(2029, 4, 1), units=50, status="scheduled"),
        VestingEvent(grant_id="G-002", vest_date=date(2027, 1, 1), units=50, status="scheduled"),
        VestingEvent(grant_id="G-002", vest_date=date(2028, 1, 1), units=50, status="scheduled"),
    ])
    for year, month in [(2025, 12)] + [(2026, month) for month in range(1, 12)]:
        day = date(year, month, 1)
        db.add_all([
            PayrollContribution(employee_id="EMP-001", month=day, amount_jpy=20000),
            SharePurchase(employee_id="EMP-001", purchase_date=day, shares=4, price_jpy=5000, amount_jpy=20000),
            PensionContribution(employee_id="EMP-001", contribution_date=day, employee_amount_jpy=15000, employer_amount_jpy=20000),
        ])
    for month in range(1, 7):
        day = date(2026, month, 1)
        db.add_all([
            PayrollContribution(employee_id="EMP-002", month=day, amount_jpy=10000),
            SharePurchase(employee_id="EMP-002", purchase_date=day, shares=1, price_jpy=10000, amount_jpy=10000),
        ])
    db.add_all([
        PayrollContribution(employee_id="SEC-001", month=date(2026, 11, 1), amount_jpy=12000),
        SharePurchase(employee_id="SEC-001", purchase_date=date(2026, 11, 1), shares=3, price_jpy=4000, amount_jpy=12000),
        PensionContribution(employee_id="EMP-002", contribution_date=date(2026, 11, 1), employee_amount_jpy=10000, employer_amount_jpy=15000),
        PensionContribution(employee_id="EMP-003", contribution_date=date(2026, 11, 1), employee_amount_jpy=8000, employer_amount_jpy=10000),
        PensionContribution(employee_id="SEC-001", contribution_date=date(2026, 11, 1), employee_amount_jpy=12000, employer_amount_jpy=14000),
    ])
    for employee_id, allocation in {
        "EMP-001": [("Domestic equity", 45), ("Global equity", 35), ("Bonds", 20)],
        "EMP-002": [("Domestic equity", 30), ("Global equity", 30), ("Bonds", 40)],
        "EMP-003": [("Domestic equity", 20), ("Global equity", 40), ("Bonds", 40)],
        "SEC-001": [("Domestic equity", 40), ("Global equity", 30), ("Bonds", 30)],
    }.items():
        db.add_all(PensionAllocation(employee_id=employee_id, asset_class=name, percentage=pct) for name, pct in allocation)
    db.commit()


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed(session)
    print("NMR synthetic demo database ready")
