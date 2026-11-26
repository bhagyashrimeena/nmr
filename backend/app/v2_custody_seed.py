"""Separate custody inventory, cash entitlements and corporate action fixtures."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CustodyAccount, CustodyPosition, CustodySecurity, Dividend, DividendDetail, Employee
from .v2_models import (CustodyAccountV2, CustodyActionV2, CustodyDividendV2,
                        FinancialEvent, OperationalStatement)
from .v2_seed import SNAPSHOT, at_day


def seed_custody(db: Session):
    opening = {}
    for account in db.scalars(select(CustodyAccount)):
        employee = db.get(Employee, account.employee_id)
        instrument = {"toyota-demo": "Toyota Motor ordinary shares",
                      "secondary-demo": "Sakura Mobility ordinary shares",
                      "asterfield": "Asterfield Industries ordinary shares"}[employee.tenant_id]
        opening[employee.id] = sum((row.quantity for row in db.scalars(select(CustodyPosition).where(
            CustodyPosition.employee_id == employee.id, CustodyPosition.instrument == instrument))), 0)
        security = db.get(CustodySecurity, instrument)
        if not db.get(CustodyAccountV2, account.account_id):
            db.add(CustodyAccountV2(id=account.account_id, tenant_id=employee.tenant_id,
                                    employee_id=employee.id, status="ACTIVE",
                                    security_id=security.security_id, instrument=instrument))
        event_id = f"CU-OPEN-{employee.id}"
        if not db.get(FinancialEvent, event_id):
            db.add(FinancialEvent(id=event_id, tenant_id=employee.tenant_id, employee_id=employee.id,
                                  service="custody", event_type="OPENING_POSITION",
                                  source_reference=account.account_id, idempotency_key=event_id,
                                  correlation_id=None, occurred_at=at_day(account.opened_on),
                                  effective_at=at_day(account.opened_on), recorded_at=SNAPSHOT,
                                  amount_jpy=Decimal("0"), quantity=Decimal(opening[employee.id]),
                                  currency="JPY", actor="custody-operations"))
        elif db.get(FinancialEvent, event_id).quantity != Decimal(opening[employee.id]):
            # Earlier local V2 fixtures had a smaller opening lot. Correct by a new event.
            correction_id = f"CU-OPEN-CORRECTION-{employee.id}"
            if not db.get(FinancialEvent, correction_id):
                delta = Decimal(opening[employee.id]) - db.get(FinancialEvent, event_id).quantity
                db.add(FinancialEvent(id=correction_id, tenant_id=employee.tenant_id,
                                      employee_id=employee.id, service="custody",
                                      event_type="OPENING_CORRECTION", source_reference=account.account_id,
                                      idempotency_key=correction_id, correlation_id=event_id,
                                      occurred_at=SNAPSHOT, effective_at=SNAPSHOT, recorded_at=SNAPSHOT,
                                      amount_jpy=Decimal("0"), quantity=delta, currency="JPY",
                                      actor="custody-operations"))
        statement_id = f"CU-STMT-{employee.id}-2026"
        if not db.get(OperationalStatement, statement_id):
            db.add(OperationalStatement(id=statement_id, tenant_id=employee.tenant_id,
                                        employee_id=employee.id, service="custody", period="2026",
                                        as_of=SNAPSHOT.date(), version=1,
                                        source_reference=account.account_id))
    db.flush()
    for dividend in db.scalars(select(Dividend)):
        account = db.scalar(select(CustodyAccountV2).where(CustodyAccountV2.employee_id == dividend.employee_id))
        detail = db.get(DividendDetail, dividend.id)
        dividend_id = f"CU-DIV-{dividend.id}"
        if not db.get(CustodyDividendV2, dividend_id):
            db.add(CustodyDividendV2(id=dividend_id, account_id=account.id,
                                     record_date=detail.record_date, payment_date=dividend.payment_date,
                                     entitlement_units=Decimal(opening[dividend.employee_id]),
                                     amount_jpy=Decimal(dividend.amount_jpy), state="PAID"))
        elif db.get(CustodyDividendV2, dividend_id).entitlement_units != Decimal(opening[dividend.employee_id]):
            db.get(CustodyDividendV2, dividend_id).entitlement_units = Decimal(opening[dividend.employee_id])
        event_id = f"CU-CASH-{dividend.id}"
        if not db.get(FinancialEvent, event_id):
            db.add(FinancialEvent(id=event_id, tenant_id=account.tenant_id, employee_id=dividend.employee_id,
                                  service="custody", event_type="DIVIDEND_PAID", source_reference=dividend_id,
                                  idempotency_key=event_id, correlation_id=None,
                                  occurred_at=at_day(dividend.payment_date), effective_at=at_day(dividend.payment_date),
                                  recorded_at=SNAPSHOT, amount_jpy=Decimal(dividend.amount_jpy),
                                  quantity=Decimal("0"), currency="JPY", actor="custody-operations"))
    if not db.get(CustodyDividendV2, "CU-DIV-SCHEDULED"):
        account = db.scalar(select(CustodyAccountV2).where(CustodyAccountV2.employee_id == "EMP-001"))
        db.add(CustodyDividendV2(id="CU-DIV-SCHEDULED", account_id=account.id,
                                 record_date=date(2026, 11, 20), payment_date=date(2026, 12, 15),
                                 entitlement_units=Decimal("120"), amount_jpy=Decimal("2500"), state="SCHEDULED"))
    elif db.get(CustodyDividendV2, "CU-DIV-SCHEDULED").entitlement_units == Decimal("100"):
        db.get(CustodyDividendV2, "CU-DIV-SCHEDULED").entitlement_units = Decimal("120")
    if not db.get(CustodyActionV2, "CU-SPLIT-001"):
        account = db.scalar(select(CustodyAccountV2).where(CustodyAccountV2.employee_id == "EMP-001"))
        db.add(CustodyActionV2(id="CU-SPLIT-001", tenant_id=account.tenant_id,
                               account_id=account.id, action_type="STOCK_SPLIT",
                               record_date=date(2026, 11, 20), effective_date=date(2026, 11, 26),
                               numerator=2, denominator=1, eligible_units=None, added_units=None,
                               state="ANNOUNCED"))
    db.commit()
