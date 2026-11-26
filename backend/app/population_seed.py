"""Deterministic, additive participant and client relationships for local operations."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import SERVICES
from .models import (CustodyAccount, CustodyPosition, CustodySecurity, CustodyValuation,
                     Employee, EquityGrant, EquityGrantDetail, McpSetting, PayrollContribution,
                     PensionAccount, PensionAllocation, PensionContribution, PensionValuation,
                     SharePurchase, StockAccount, StockIncentive, StockPlanDetail, Tenant,
                     TenantServiceSetting, VestingEvent, WellnessProgress)
from .v2_models import ClientServiceAgreement, EmployeeProfile, ParticipantOperationalProfile


CLIENTS = (
    ("toyota-demo", "TYO", "Toyota", "TOYOTA-SHARE-01", "Toyota Motor ordinary shares", 10000, 5000, 5),
    ("secondary-demo", "SAK", "Sakura Mobility", "SAKURA-SHARE-01", "Sakura Mobility ordinary shares", 12000, 4000, 0),
    ("asterfield", "AST", "Asterfield Industries", "ASTER-SHARE-01", "Asterfield Industries ordinary shares", 9000, 3000, 0),
)
GIVEN = ("Rin", "Nao", "Emi", "Sora", "Haru", "Aya", "Mika", "Ren", "Mio", "Kira", "Tomo", "Yuna")
FAMILY = ("Aoba", "Hoshida", "Mizuki", "Arata", "Komori", "Yamane", "Ishiba")
DEPARTMENTS = ("Manufacturing", "Engineering", "Finance", "Operations", "Sales", "Technology")


def seed_population(db: Session):
    """Add 252 varied participants; retain all earlier records and policy decisions."""
    for tenant_id, prefix, name, plan_id, instrument, monthly, price, incentive_pct in CLIENTS:
        if not db.get(Tenant, tenant_id):
            db.add(Tenant(id=tenant_id, name=name))
        if not db.get(McpSetting, tenant_id):
            db.add(McpSetting(tenant_id=tenant_id, enabled=True,
                              changed_by="seed", reason="Initial access setting"))
        for service in SERVICES:
            if not db.scalar(select(TenantServiceSetting.id).where(
                TenantServiceSetting.tenant_id == tenant_id,
                TenantServiceSetting.service == service)):
                db.add(TenantServiceSetting(tenant_id=tenant_id, service=service, enabled=True,
                                            changed_by="seed", reason="Initial service setting"))
        if not db.get(CustodySecurity, instrument):
            db.add(CustodySecurity(instrument=instrument, security_id=f"NMR-{prefix}-ORD",
                                   asset_class="equity", illustrative_price_jpy=Decimal(price)))
        if db.get(Employee, f"{prefix}-0084"):
            continue
        for number in range(1, 85):
            employee_id = f"{prefix}-{number:04d}"
            if db.get(Employee, employee_id):
                continue
            recent = number % 11 == 0
            nearing_retirement = number % 13 == 0
            active = number % 17 != 0
            has_stock = number % 4 != 0
            has_custody = number % 3 == 0
            has_equity = number % 5 == 0
            joined = date(2026, 9, 1) if recent else date(2023 + number % 2, 4, 1)
            months = (9, 10) if recent else (5, 6, 7, 8, 9, 10)
            services = ["pension", "wellness"]
            if has_stock:
                services.append("stock")
            if has_custody:
                services.append("custody")
            if has_equity:
                services.append("equity")
            db.add(Employee(id=employee_id, tenant_id=tenant_id,
                            display_name=f"{GIVEN[(number - 1) % len(GIVEN)]} {FAMILY[(number - 1) // len(GIVEN)]}",
                            active=active, allowed_services=",".join(services)))
            db.add(ParticipantOperationalProfile(employee_id=employee_id,
                                                 department=DEPARTMENTS[(number - 1) % len(DEPARTMENTS)],
                                                 cohort="RECENT_JOINER" if recent else
                                                 "NEARING_RETIREMENT" if nearing_retirement else
                                                 "TERMINATED" if not active else "ESTABLISHED",
                                                 hired_on=joined,
                                                 left_on=date(2026, 10, 31) if not active else None))
            opening = 3200000 if nearing_retirement else 90000 if recent else 700000 + number * 6000
            change = -6000 if number % 9 == 0 else 12000
            employee_contrib, employer_contrib = 8000 + (number % 3) * 1000, 12000
            closing = opening + change + len(months) * (employee_contrib + employer_contrib)
            db.add(PensionAccount(employee_id=employee_id, account_type="Corporate defined contribution",
                                  opening_balance_jpy=opening, investment_change_jpy=change))
            db.add_all(PensionAllocation(employee_id=employee_id, asset_class=asset_class, percentage=pct)
                       for asset_class, pct in (("Domestic equity", 40), ("Global equity", 35), ("Bonds", 25)))
            db.add_all((PensionValuation(employee_id=employee_id, valuation_date=day,
                                         balance_jpy=value, illustrative_nav=Decimal(nav))
                        for day, value, nav in ((date(2025, 11, 25), opening, "100.0000"),
                                                (date(2026, 11, 25), closing, "104.0000"))))
            for month in months:
                period = date(2026, month, 1)
                db.add(PensionContribution(employee_id=employee_id, contribution_date=period,
                                           employee_amount_jpy=employee_contrib,
                                           employer_amount_jpy=employer_contrib))
            if has_stock:
                opening_shares = 5 + number % 16
                db.add(StockAccount(employee_id=employee_id, plan_id=plan_id,
                                    opening_shares=opening_shares, monthly_contribution_jpy=monthly))
                db.add(StockPlanDetail(employee_id=employee_id,
                                       plan_name=f"{name} Employee Shareholding Association",
                                       enrollment_date=joined,
                                       participation_status="active" if active else "left",
                                       opening_cost_jpy=opening_shares * price,
                                       employer_incentive_percent=incentive_pct,
                                       illustrative_price_jpy=Decimal(price)))
                for month in months:
                    period = date(2026, month, 1)
                    db.add(PayrollContribution(employee_id=employee_id, month=period,
                                               amount_jpy=monthly))
                    db.add(SharePurchase(employee_id=employee_id, purchase_date=period,
                                         shares=monthly // price, price_jpy=price, amount_jpy=monthly))
                    if incentive_pct:
                        db.add(StockIncentive(employee_id=employee_id, month=period,
                                              amount_jpy=monthly * incentive_pct // 100))
            if has_custody:
                quantity = 10 + number % 18
                db.add(CustodyAccount(employee_id=employee_id, account_id=f"CUST-{employee_id}",
                                      opened_on=joined, account_status="active" if active else "inactive"))
                db.add(CustodyPosition(employee_id=employee_id, instrument=instrument, quantity=quantity))
                db.add(CustodyValuation(employee_id=employee_id, valuation_date=date(2026, 11, 25),
                                        illustrative_value_jpy=quantity * price))
            if has_equity:
                award_type = ("RSU", "PSU", "Option")[number % 3]
                grant_id = f"G-{employee_id}"
                forfeited = 20 if not active else 0
                db.add(EquityGrant(id=grant_id, employee_id=employee_id,
                                   award_type=award_type, granted_units=100,
                                   grant_date=date(2025, 4, 1)))
                db.add(EquityGrantDetail(grant_id=grant_id, plan_name=f"{name} Equity Awards Plan",
                                         vesting_condition="Continued employment and award conditions",
                                         exercise_price_jpy=Decimal(price - 300) if award_type == "Option" else None,
                                         expiry_date=date(2035, 4, 1) if award_type == "Option" else None,
                                         forfeited_units=forfeited, released_units=0, exercised_units=0,
                                         illustrative_share_price_jpy=Decimal(price)))
                db.add(VestingEvent(grant_id=grant_id, vest_date=date(2026, 4, 1),
                                    units=20, status="vested"))
                db.add(VestingEvent(grant_id=grant_id, vest_date=date(2027, 4, 1),
                                    units=80 - forfeited, status="scheduled"))
            db.add(WellnessProgress(employee_id=employee_id, resource_id="W-RET-01",
                                    status="completed" if number % 3 == 0 else "in_progress"))
    db.commit()


def seed_service_agreements(db: Session):
    for employee_id, department in (("EMP-001", "Engineering"), ("EMP-002", "Manufacturing"),
                                    ("EMP-003", "Finance"), ("SEC-001", "Operations")):
        if not db.get(ParticipantOperationalProfile, employee_id):
            existing = db.get(EmployeeProfile, employee_id)
            db.add(ParticipantOperationalProfile(employee_id=employee_id, department=department,
                                                 cohort="ESTABLISHED", hired_on=existing.hired_on,
                                                 left_on=existing.left_on))
    for tenant_id, prefix, *_ in CLIENTS:
        entity_id = f"LE-{prefix}" if tenant_id == "asterfield" else (
            "LE-TOYOTA" if tenant_id == "toyota-demo" else "LE-SAKURA")
        for service in SERVICES:
            agreement_id = f"AGR-{prefix}-{service.upper()}"
            if not db.get(ClientServiceAgreement, agreement_id):
                db.add(ClientServiceAgreement(id=agreement_id, tenant_id=tenant_id,
                                              legal_entity_id=entity_id, service=service,
                                              effective_on=date(2024, 4, 1), status="ACTIVE",
                                              source_reference=f"{prefix}-WORKPLACE-2024/{service.upper()}"))
    db.commit()
