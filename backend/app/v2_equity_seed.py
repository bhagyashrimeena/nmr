"""Repeatable grant, tranche, reserve and release fixtures."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Employee, EquityGrant, EquityGrantDetail, VestingEvent
from .v2_models import EquityAward, EquityPlanV2, EquityRelease, EquityTranche, OperationalStatement, ReconciliationCase


def seed_equity(db: Session):
    plans = {"toyota-demo": ("EQ-TOYOTA", "Toyota Equity Awards Plan", 10000),
             "secondary-demo": ("EQ-SAKURA", "Sakura Equity Awards Plan", 2000)}
    for tenant_id, (plan_id, name, reserve) in plans.items():
        if not db.get(EquityPlanV2, plan_id):
            db.add(EquityPlanV2(id=plan_id, tenant_id=tenant_id, name=name,
                                authorized_units=reserve, acceptance_required=False, status="ACTIVE"))
    db.flush()
    for grant in db.scalars(select(EquityGrant).order_by(EquityGrant.id)):
        employee = db.get(Employee, grant.employee_id)
        detail = db.get(EquityGrantDetail, grant.id)
        if not db.get(EquityAward, grant.id):
            db.add(EquityAward(id=grant.id, plan_id=plans[employee.tenant_id][0],
                               employee_id=grant.employee_id, award_type=grant.award_type,
                               granted_units=grant.granted_units, grant_date=grant.grant_date,
                               state="ACTIVE", strike_jpy=detail.exercise_price_jpy,
                               expiry_date=detail.expiry_date, released_units=detail.released_units,
                               exercised_units=detail.exercised_units, forfeited_units=detail.forfeited_units))
        for vest in db.scalars(select(VestingEvent).where(VestingEvent.grant_id == grant.id)):
            tranche_id = f"TR-{grant.id}-{vest.id}"
            if not db.get(EquityTranche, tranche_id):
                db.add(EquityTranche(id=tranche_id, award_id=grant.id, vest_date=vest.vest_date,
                                     units=vest.units, state=vest.status.upper()))
        statement_id = f"EQ-STMT-{grant.id}-2026"
        if not db.get(OperationalStatement, statement_id):
            db.add(OperationalStatement(id=statement_id, tenant_id=employee.tenant_id,
                                        employee_id=employee.id, service="equity", period="2026",
                                        as_of=date(2026, 11, 26), version=1, source_reference=grant.id))
    if not db.get(EquityAward, "G-PROPOSED-001"):
        db.add(EquityAward(id="G-PROPOSED-001", plan_id="EQ-TOYOTA", employee_id="EMP-002",
                           award_type="RSU", granted_units=120, grant_date=date(2026, 11, 20),
                           state="PROPOSED", strike_jpy=None, expiry_date=None,
                           released_units=0, exercised_units=0, forfeited_units=0))
    for tranche_id, vest_date in [("TR-PROPOSED-1", date(2027, 11, 20)),
                                  ("TR-PROPOSED-2", date(2028, 11, 20))]:
        if not db.get(EquityTranche, tranche_id):
            db.add(EquityTranche(id=tranche_id, award_id="G-PROPOSED-001",
                                 vest_date=vest_date, units=60, state="SCHEDULED"))
    if not db.get(EquityRelease, "REL-G-001"):
        db.add(EquityRelease(id="REL-G-001", award_id="G-001", employee_id="EMP-001",
                             units=20, withholding_units=5, state="PREPARED", custody_confirmation=None))
    if not db.get(ReconciliationCase, "EQ-CASE-001"):
        db.add(ReconciliationCase(id="EQ-CASE-001", tenant_id="toyota-demo", service="equity",
                                  employee_id="EMP-002", source_reference="G-PROPOSED-001",
                                  break_type="GRANT_APPROVAL_PENDING", expected_jpy=None, actual_jpy=None,
                                  status="OPEN", owner="Equity operations"))
    db.commit()
