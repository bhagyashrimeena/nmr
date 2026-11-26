"""Dated pension funds, units, contributions and account events."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Employee, PensionAccount, PensionAllocation, PensionContribution
from .v2_models import (
    FinancialEvent, OperationalStatement, PensionContributionRecord, PensionFund,
    PensionFundPosition, PensionFutureAllocation, PensionNav, PensionPlanV2,
    PensionAllocationInstruction, PensionInstructionLine, ReconciliationCase,
)
from .v2_seed import SNAPSHOT, at_day

FUNDS = [
    ("DOM", "Domestic equity index", "Domestic equity", Decimal("100"), Decimal("0.15")),
    ("GLB", "Global equity index", "Global equity", Decimal("125"), Decimal("0.22")),
    ("BND", "Bond index", "Bonds", Decimal("80"), Decimal("0.10")),
]


def pension_event(db: Session, event_id: str, tenant_id: str, employee_id: str,
                  event_type: str, source: str, occurred_at: datetime, amount: Decimal):
    if db.get(FinancialEvent, event_id):
        return
    db.add(FinancialEvent(id=event_id, tenant_id=tenant_id, employee_id=employee_id,
                          service="pension", event_type=event_type, source_reference=source,
                          idempotency_key=event_id, occurred_at=occurred_at, effective_at=occurred_at,
                          recorded_at=SNAPSHOT, amount_jpy=amount, quantity=Decimal("0"),
                          actor="nmr-operations"))


def seed_pension(db: Session):
    for tenant_id, prefix in [("toyota-demo", "TOYOTA"), ("secondary-demo", "SAKURA")]:
        plan_id = f"PEN-{prefix}"
        if not db.get(PensionPlanV2, plan_id):
            db.add(PensionPlanV2(id=plan_id, tenant_id=tenant_id,
                                 name=f"{prefix.title()} Corporate Defined Contribution Plan",
                                 status="ACTIVE", effective_on=date(2022, 4, 1)))
        for code, name, category, current_nav, fee in FUNDS:
            fund_id = f"{prefix}-{code}"
            if not db.get(PensionFund, fund_id):
                db.add(PensionFund(id=fund_id, plan_id=plan_id, name=name,
                                   category=category, annual_fee_percent=fee, eligible=True))
            for valuation_date, nav in [(date(2026, 10, 26), current_nav * Decimal("0.98")),
                                        (SNAPSHOT.date(), current_nav)]:
                nav_id = f"NAV-{fund_id}-{valuation_date:%Y%m%d}"
                if not db.get(PensionNav, nav_id):
                    db.add(PensionNav(id=nav_id, fund_id=fund_id,
                                      valuation_date=valuation_date, nav_jpy=nav))
    db.flush()

    for account in db.scalars(select(PensionAccount)):
        employee = db.get(Employee, account.employee_id)
        prefix = "TOYOTA" if employee.tenant_id == "toyota-demo" else "SAKURA"
        contributions = db.scalars(select(PensionContribution).where(
            PensionContribution.employee_id == account.employee_id)).all()
        balance = Decimal(account.opening_balance_jpy + account.investment_change_jpy) + sum(
            (Decimal(row.employee_amount_jpy + row.employer_amount_jpy) for row in contributions), Decimal("0"))
        pension_event(db, f"EV-PEN-OPEN-{account.employee_id}", employee.tenant_id, account.employee_id,
                      "OPENING_BALANCE", f"PEN-{prefix}", at_day(date(2025, 11, 25)),
                      Decimal(account.opening_balance_jpy))
        pension_event(db, f"EV-PEN-RETURN-{account.employee_id}", employee.tenant_id, account.employee_id,
                      "INVESTMENT_CHANGE", f"PEN-{prefix}", SNAPSHOT,
                      Decimal(account.investment_change_jpy))
        for contribution in contributions:
            source = f"PEN-CONTRIB-{contribution.id:05d}"
            if not db.get(PensionContributionRecord, source):
                db.add(PensionContributionRecord(
                    id=source, employee_id=account.employee_id, source_reference=source,
                    period=contribution.contribution_date, employee_jpy=Decimal(contribution.employee_amount_jpy),
                    employer_jpy=Decimal(contribution.employer_amount_jpy), state="INVESTED"))
            pension_event(db, f"EV-{source}", employee.tenant_id, account.employee_id,
                          "CONTRIBUTION_INVESTED", source, at_day(contribution.contribution_date),
                          Decimal(contribution.employee_amount_jpy + contribution.employer_amount_jpy))
        for allocation in db.scalars(select(PensionAllocation).where(
            PensionAllocation.employee_id == account.employee_id)):
            code, _, _, nav, _ = next(item for item in FUNDS if item[2] == allocation.asset_class)
            fund_id = f"{prefix}-{code}"
            position_id = f"POS-{account.employee_id}-{code}"
            if not db.get(PensionFundPosition, position_id):
                value = balance * Decimal(allocation.percentage) / Decimal("100")
                db.add(PensionFundPosition(id=position_id, employee_id=account.employee_id,
                                           fund_id=fund_id, units=value / nav, as_of=SNAPSHOT.date()))
            future_id = f"FUT-{account.employee_id}-{code}"
            if not db.get(PensionFutureAllocation, future_id):
                db.add(PensionFutureAllocation(id=future_id, employee_id=account.employee_id,
                                               fund_id=fund_id, percentage=Decimal(allocation.percentage),
                                               effective_period=date(2026, 12, 1)))
        statement_id = f"STMT-PEN-{account.employee_id}-2026"
        if not db.get(OperationalStatement, statement_id):
            db.add(OperationalStatement(id=statement_id, tenant_id=employee.tenant_id,
                                        employee_id=account.employee_id, service="pension",
                                        period="2026", as_of=SNAPSHOT.date(), version=1,
                                        source_reference=f"PEN-{prefix}"))

    if not db.get(PensionContributionRecord, "PEN-REJ-001"):
        db.add(PensionContributionRecord(id="PEN-REJ-001", employee_id="EMP-003",
                                         source_reference="PEN-REJ-001", period=date(2026, 10, 1),
                                         employee_jpy=Decimal("8000"), employer_jpy=Decimal("10000"),
                                         state="REJECTED", rejection_reason="Plan enrollment reference requires review"))
    if not db.get(ReconciliationCase, "BREAK-PEN-001"):
        db.add(ReconciliationCase(id="BREAK-PEN-001", tenant_id="toyota-demo",
                                  service="pension", employee_id="EMP-003",
                                  source_reference="PEN-REJ-001", break_type="REJECTED_CONTRIBUTION",
                                  expected_jpy=Decimal("18000"), actual_jpy=Decimal("0"),
                                  status="OPEN", owner="Pension operations"))
    if not db.get(PensionAllocationInstruction, "PEN-INST-001"):
        db.add(PensionAllocationInstruction(id="PEN-INST-001", tenant_id="toyota-demo",
                                            employee_id="EMP-001", state="DRAFT",
                                            idempotency_key="seed-allocation-001",
                                            submitted_at=SNAPSHOT))
        for code, percentage in [("DOM", 40), ("GLB", 40), ("BND", 20)]:
            db.add(PensionInstructionLine(id=f"PEN-INST-001-{code}",
                                          instruction_id="PEN-INST-001",
                                          fund_id=f"TOYOTA-{code}",
                                          percentage=Decimal(percentage)))
    db.commit()

