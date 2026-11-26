"""Deterministic fictional records; safe to call repeatedly on an existing demo DB."""
from datetime import date

from decimal import Decimal

from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .catalog import SERVICES
from .models import (CorporateAction, CorporateActionDetail, CustodyAccount, CustodyPosition,
                     CustodySecurity, CustodySettlement, CustodyValuation, Dividend, DividendDetail, Employee,
                     EquityGrant, EquityGrantDetail, McpSetting, PayrollContribution,
                     PensionAccount, PensionAllocation, PensionContribution, PensionValuation,
                     SharePurchase, StockAccount, StockIncentive, StockPlanDetail, Tenant,
                     TenantServiceSetting, VestingEvent, WellnessPreference, WellnessProgress,
                     WellnessResource)

AS_OF = date(2026, 11, 25)


def refresh_display_labels(db):
    """Refresh earlier fixture labels without changing account values or access policies."""
    replacements = [
        (Tenant, "name", "Toyota · hypothetical client", "Toyota"),
        (Tenant, "name", "Sakura Mobility · fictional client", "Sakura Mobility"),
        (McpSetting, "reason", "Initial demo setting", "Initial access setting"),
        (StockAccount, "plan_id", "TDEMO-SHARE-01", "TOYOTA-SHARE-01"),
        (StockAccount, "plan_id", "SDEMO-SHARE-01", "SAKURA-SHARE-01"),
        (StockPlanDetail, "plan_name", "Employee Shareholding Association · Demo", "Toyota Employee Shareholding Association"),
        (StockPlanDetail, "plan_name", "Sakura Employee Share Plan · Demo", "Sakura Employee Share Plan"),
        (CustodyPosition, "instrument", "TDEMO ordinary shares", "Toyota Motor ordinary shares"),
        (CustodyPosition, "instrument", "SDEMO ordinary shares", "Sakura Mobility ordinary shares"),
        (CustodyPosition, "instrument", "Demo government bond basket", "Japanese government bond fund"),
        (Dividend, "instrument", "TDEMO ordinary shares", "Toyota Motor ordinary shares"),
        (Dividend, "instrument", "SDEMO ordinary shares", "Sakura Mobility ordinary shares"),
        (CorporateAction, "instrument", "TDEMO ordinary shares", "Toyota Motor ordinary shares"),
        (CorporateAction, "instrument", "SDEMO ordinary shares", "Sakura Mobility ordinary shares"),
        (CorporateAction, "title", "Illustrative year-end dividend announcement", "Year-end dividend announcement"),
        (CustodySettlement, "instrument", "TDEMO ordinary shares", "Toyota Motor ordinary shares"),
        (CustodySettlement, "instrument", "Demo government bond basket", "Japanese government bond fund"),
        (CustodySecurity, "instrument", "TDEMO ordinary shares", "Toyota Motor ordinary shares"),
        (CustodySecurity, "instrument", "SDEMO ordinary shares", "Sakura Mobility ordinary shares"),
        (CustodySecurity, "instrument", "Demo government bond basket", "Japanese government bond fund"),
        (CustodySecurity, "security_id", "DEMO-TYO-7203", "NMR-TM-7203"),
        (CustodySecurity, "security_id", "DEMO-SAK-1001", "NMR-SAK-1001"),
        (CustodySecurity, "security_id", "DEMO-JGB-2026", "NMR-JGB-2026"),
        (EquityGrantDetail, "plan_name", "Synthetic Equity Awards Plan", "Equity Awards Plan"),
    ]
    for model, field, previous, current in replacements:
        column = getattr(model, field)
        for row in db.scalars(select(model).where(column == previous)):
            setattr(row, field, current)
    db.flush()


def seed(db):
    if db.scalar(select(Tenant.id).limit(1)):
        seed_extensions(db)
        return
    db.add_all([
        Tenant(id="toyota-demo", name="Toyota"),
        Tenant(id="secondary-demo", name="Sakura Mobility"),
        McpSetting(tenant_id="toyota-demo", enabled=True, changed_by="seed", reason="Initial access setting"),
        McpSetting(tenant_id="secondary-demo", enabled=True, changed_by="seed", reason="Initial access setting"),
        Employee(id="EMP-001", tenant_id="toyota-demo", display_name="Aiko Mori", allowed_services="stock,pension,wellness,custody,equity"),
        Employee(id="EMP-002", tenant_id="toyota-demo", display_name="Kenji Sato", allowed_services="stock,pension,wellness,custody,equity"),
        Employee(id="EMP-003", tenant_id="toyota-demo", display_name="Yui Tanaka", allowed_services="pension,wellness,equity"),
        Employee(id="SEC-001", tenant_id="secondary-demo", display_name="Hana Kato", allowed_services="stock,pension,wellness,custody,equity"),
        StockAccount(employee_id="EMP-001", plan_id="TOYOTA-SHARE-01", opening_shares=72, monthly_contribution_jpy=20000),
        StockAccount(employee_id="EMP-002", plan_id="TOYOTA-SHARE-01", opening_shares=30, monthly_contribution_jpy=10000),
        StockAccount(employee_id="SEC-001", plan_id="SAKURA-SHARE-01", opening_shares=10, monthly_contribution_jpy=12000),
        PensionAccount(employee_id="EMP-001", account_type="Corporate defined contribution", opening_balance_jpy=3000000, investment_change_jpy=80000),
        PensionAccount(employee_id="EMP-002", account_type="Corporate defined contribution", opening_balance_jpy=1800000, investment_change_jpy=25000),
        PensionAccount(employee_id="EMP-003", account_type="Corporate defined contribution", opening_balance_jpy=640000, investment_change_jpy=-8000),
        PensionAccount(employee_id="SEC-001", account_type="Corporate defined contribution", opening_balance_jpy=920000, investment_change_jpy=14000),
        WellnessResource(id="W-RET-01", title="Share plans and retirement saving", topic="retirement", description="How payroll share purchases differ from pension contributions.", content="A shareholding plan buys company shares with employee contributions. A corporate pension invests for retirement under its plan rules. Both involve risk; neither is a guaranteed return."),
        WellnessResource(id="W-BUD-01", title="Building an emergency buffer", topic="budgeting", description="A plain-language guide to setting aside short-term cash.", content="Review regular spending and choose a savings target that fits your circumstances. This educational guide is not personal financial advice."),
        WellnessResource(id="W-EQ-01", title="Understanding restricted stock units", topic="equity", description="Grant, vesting, and holding are different events.", content="An RSU award is distinct from shares purchased through payroll. Vesting schedules and tax treatment depend on plan terms. Consult the plan documents for details."),
        CustodyPosition(employee_id="EMP-001", instrument="Toyota Motor ordinary shares", quantity=120),
        CustodyPosition(employee_id="EMP-002", instrument="Toyota Motor ordinary shares", quantity=36),
        CustodyPosition(employee_id="SEC-001", instrument="Sakura Mobility ordinary shares", quantity=13),
        Dividend(employee_id="EMP-001", payment_date=date(2026, 9, 30), instrument="Toyota Motor ordinary shares", amount_jpy=6000, status="credited"),
        Dividend(employee_id="EMP-002", payment_date=date(2026, 9, 30), instrument="Toyota Motor ordinary shares", amount_jpy=1800, status="credited"),
        Dividend(employee_id="SEC-001", payment_date=date(2026, 9, 30), instrument="Sakura Mobility ordinary shares", amount_jpy=520, status="credited"),
        CorporateAction(id="CA-01", instrument="Toyota Motor ordinary shares", title="Annual dividend record date notice", effective_date=date(2026, 9, 1)),
        CorporateAction(id="CA-02", instrument="Sakura Mobility ordinary shares", title="Annual dividend record date notice", effective_date=date(2026, 9, 1)),
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
    seed_extensions(db)


def seed_extensions(db):
    """Add new POC detail records without resetting an existing local demo database."""
    refresh_display_labels(db)
    for tenant_id in db.scalars(select(Tenant.id)):
        for service in SERVICES:
            existing = db.scalar(select(TenantServiceSetting).where(
                TenantServiceSetting.tenant_id == tenant_id,
                TenantServiceSetting.service == service))
            if not existing:
                db.add(TenantServiceSetting(tenant_id=tenant_id, service=service, enabled=True,
                                            changed_by="seed", reason="Initial service setting"))

    stock_details = {
        "EMP-001": ("Toyota Employee Shareholding Association", date(2023, 4, 1), 338400, 5, "5300.00"),
        "EMP-002": ("Toyota Employee Shareholding Association", date(2024, 7, 1), 270000, 0, "10300.00"),
        "SEC-001": ("Sakura Employee Share Plan", date(2025, 6, 1), 38000, 0, "4200.00"),
    }
    for employee_id, (name, enrollment, opening_cost, incentive_pct, price) in stock_details.items():
        if db.get(StockAccount, employee_id) and not db.get(StockPlanDetail, employee_id):
            db.add(StockPlanDetail(employee_id=employee_id, plan_name=name,
                                   enrollment_date=enrollment, participation_status="active",
                                   opening_cost_jpy=opening_cost, employer_incentive_percent=incentive_pct,
                                   illustrative_price_jpy=Decimal(price)))
    if not db.scalar(select(StockIncentive.id).where(StockIncentive.employee_id == "EMP-001").limit(1)):
        for contribution in db.scalars(select(PayrollContribution).where(PayrollContribution.employee_id == "EMP-001")):
            db.add(StockIncentive(employee_id="EMP-001", month=contribution.month,
                                  amount_jpy=contribution.amount_jpy * 5 // 100))

    for employee_id in db.scalars(select(PensionAccount.employee_id)):
        if db.scalar(select(PensionValuation.id).where(PensionValuation.employee_id == employee_id).limit(1)):
            continue
        account = db.get(PensionAccount, employee_id)
        contributions = db.scalars(select(PensionContribution).where(PensionContribution.employee_id == employee_id)).all()
        closing = account.opening_balance_jpy + account.investment_change_jpy + sum(
            c.employee_amount_jpy + c.employer_amount_jpy for c in contributions)
        db.add_all([
            PensionValuation(employee_id=employee_id, valuation_date=date(2025, 11, 25),
                             balance_jpy=account.opening_balance_jpy, illustrative_nav=Decimal("100.0000")),
            PensionValuation(employee_id=employee_id, valuation_date=date(2026, 5, 25),
                             balance_jpy=(account.opening_balance_jpy + closing) // 2,
                             illustrative_nav=Decimal("102.5000")),
            PensionValuation(employee_id=employee_id, valuation_date=AS_OF,
                             balance_jpy=closing, illustrative_nav=Decimal("104.0000")),
        ])

    resources = [
        ("W-INV-01", "Diversification and investment risk", "investing", "How diversified funds spread, but do not remove, market risk.", "Different assets have different risks. Diversification can reduce concentration risk but does not eliminate losses."),
        ("W-BEN-01", "Understanding workplace benefits", "benefits", "A guide to share plans, pensions, and equity awards.", "Payroll share purchases, retirement contributions, and employer equity awards have different rules and timing."),
        ("W-CUS-01", "Corporate actions and dividends", "custody", "Record dates, payment dates, and processing status.", "An announced distribution is not a paid dividend. Check the record date, payment date, and final status."),
        ("W-SHARE-01", "Reading a share purchase statement", "shareholding", "Understand units, price, purchase cost, and credited holdings.", "A purchase statement shows the quantity and cost of shares acquired through a payroll share plan."),
        ("W-RET-02", "Retirement contributions and matching", "retirement", "Employee and employer contributions in a corporate DC plan.", "Employer contributions vary by plan. Investment returns and future balances are uncertain."),
    ]
    for resource_id, title, topic, description, content in resources:
        if not db.get(WellnessResource, resource_id):
            db.add(WellnessResource(id=resource_id, title=title, topic=topic,
                                    description=description, content=content))
    for employee_id, topic in {"EMP-001": "retirement", "EMP-002": "budgeting", "EMP-003": "equity", "SEC-001": "investing"}.items():
        if not db.get(WellnessPreference, employee_id):
            db.add(WellnessPreference(employee_id=employee_id, topic=topic))
    for employee_id, resource_id, status in [
        ("EMP-001", "W-RET-01", "completed"), ("EMP-001", "W-BEN-01", "in_progress"),
        ("EMP-002", "W-BUD-01", "completed"), ("EMP-003", "W-EQ-01", "in_progress")]:
        existing = db.scalar(select(WellnessProgress).where(WellnessProgress.employee_id == employee_id,
                                                            WellnessProgress.resource_id == resource_id))
        if not existing:
            db.add(WellnessProgress(employee_id=employee_id, resource_id=resource_id, status=status))

    securities = [
        ("Toyota Motor ordinary shares", "NMR-TM-7203", "equity", "5300.00"),
        ("Sakura Mobility ordinary shares", "NMR-SAK-1001", "equity", "4200.00"),
        ("Japanese government bond fund", "NMR-JGB-2026", "fixed_income", "10000.00"),
    ]
    for instrument, security_id, asset_class, price in securities:
        if not db.get(CustodySecurity, instrument):
            db.add(CustodySecurity(instrument=instrument, security_id=security_id,
                                   asset_class=asset_class, illustrative_price_jpy=Decimal(price)))
    for employee_id in ("EMP-001", "EMP-002", "SEC-001"):
        if not db.get(CustodyAccount, employee_id):
            db.add(CustodyAccount(employee_id=employee_id, account_id=f"CUST-{employee_id}",
                                  opened_on=date(2024, 4, 1), account_status="active"))
    if not db.scalar(select(CustodyPosition.id).where(CustodyPosition.employee_id == "EMP-001",
                                                       CustodyPosition.instrument == "Japanese government bond fund")):
        db.add(CustodyPosition(employee_id="EMP-001", instrument="Japanese government bond fund", quantity=10))
    if not db.get(CustodySettlement, "SET-EMP-001-01"):
        db.add_all([
            CustodySettlement(id="SET-EMP-001-01", employee_id="EMP-001", instrument="Japanese government bond fund",
                              trade_date=date(2026, 10, 12), settlement_date=date(2026, 10, 14), quantity=10, status="settled"),
            CustodySettlement(id="SET-EMP-001-02", employee_id="EMP-001", instrument="Toyota Motor ordinary shares",
                              trade_date=date(2026, 11, 25), settlement_date=date(2026, 11, 27), quantity=4, status="pending"),
        ])
    for employee_id, snapshots in {
        "EMP-001": [(date(2026, 6, 25), 620000), (date(2026, 9, 25), 700000), (AS_OF, 736000)],
        "EMP-002": [(date(2026, 6, 25), 180000), (AS_OF, 190800)],
        "SEC-001": [(date(2026, 6, 25), 50000), (AS_OF, 54600)],
    }.items():
        if not db.scalar(select(CustodyValuation.id).where(CustodyValuation.employee_id == employee_id).limit(1)):
            db.add_all(CustodyValuation(employee_id=employee_id, valuation_date=day,
                                        illustrative_value_jpy=value) for day, value in snapshots)
    if not db.get(CorporateAction, "CA-03"):
        db.add(CorporateAction(id="CA-03", instrument="Toyota Motor ordinary shares",
                               title="Year-end dividend announcement", effective_date=date(2027, 1, 31)))
    for action_id, record_date, status in [
        ("CA-01", date(2026, 9, 1), "completed"),
        ("CA-02", date(2026, 9, 1), "completed"),
        ("CA-03", date(2026, 12, 31), "announced")]:
        if not db.get(CorporateActionDetail, action_id):
            db.add(CorporateActionDetail(action_id=action_id, record_date=record_date, status=status))
    db.flush()
    for dividend in db.scalars(select(Dividend)):
        if not db.get(DividendDetail, dividend.id):
            db.add(DividendDetail(dividend_id=dividend.id, record_date=date(2026, 9, 1)))

    if not db.get(EquityGrant, "G-003"):
        db.add(EquityGrant(id="G-003", employee_id="EMP-001", award_type="Option",
                           granted_units=100, grant_date=date(2025, 3, 1)))
        db.add_all([
            VestingEvent(grant_id="G-003", vest_date=date(2026, 3, 1), units=50, status="vested"),
            VestingEvent(grant_id="G-003", vest_date=date(2027, 3, 1), units=50, status="scheduled"),
        ])
    for grant_id, price, expiry in [
        ("G-001", None, None), ("G-002", "4700.00", date(2036, 1, 1)),
        ("G-003", "4800.00", date(2035, 3, 1))]:
        if not db.get(EquityGrantDetail, grant_id):
            db.add(EquityGrantDetail(grant_id=grant_id, plan_name="Equity Awards Plan",
                                     vesting_condition="Continued employment through vest date",
                                     exercise_price_jpy=Decimal(price) if price else None, expiry_date=expiry,
                                     forfeited_units=0, released_units=0, exercised_units=0,
                                     illustrative_share_price_jpy=Decimal("5300.00")))
    db.commit()


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed(session)
    print("NMR Workplace Finance database ready")
