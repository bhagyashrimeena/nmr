"""Read-only business summaries, independent of HTTP and authentication."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (CorporateAction, CustodyPosition, Dividend, EquityGrant,
                     PayrollContribution, PensionAccount, PensionAllocation,
                     PensionContribution, SharePurchase, StockAccount, VestingEvent,
                     WellnessResource)
from .seed import AS_OF


def stock_summary(db: Session, employee_id: str):
    account = db.get(StockAccount, employee_id)
    if not account:
        return None
    contributions = db.scalars(select(PayrollContribution).where(PayrollContribution.employee_id == employee_id).order_by(PayrollContribution.month.desc())).all()
    purchases = db.scalars(select(SharePurchase).where(SharePurchase.employee_id == employee_id).order_by(SharePurchase.purchase_date.desc())).all()
    return {"as_of": AS_OF, "currency": "JPY", "plan_id": account.plan_id,
            "shares_held": account.opening_shares + sum(p.shares for p in purchases),
            "monthly_contribution_jpy": account.monthly_contribution_jpy,
            "total_contributions_jpy": sum(c.amount_jpy for c in contributions),
            "contributions": [{"month": c.month, "amount_jpy": c.amount_jpy} for c in contributions],
            "recent_purchases": [{"purchase_date": p.purchase_date, "shares": p.shares, "price_jpy": p.price_jpy, "amount_jpy": p.amount_jpy} for p in purchases[:6]]}


def pension_summary(db: Session, employee_id: str):
    account = db.get(PensionAccount, employee_id)
    if not account:
        return None
    contributions = db.scalars(select(PensionContribution).where(PensionContribution.employee_id == employee_id).order_by(PensionContribution.contribution_date.desc())).all()
    allocations = db.scalars(select(PensionAllocation).where(PensionAllocation.employee_id == employee_id)).all()
    employee_total = sum(c.employee_amount_jpy for c in contributions)
    employer_total = sum(c.employer_amount_jpy for c in contributions)
    return {"as_of": AS_OF, "currency": "JPY", "account_type": account.account_type,
            "balance_jpy": account.opening_balance_jpy + employee_total + employer_total + account.investment_change_jpy,
            "employee_contributions_jpy": employee_total, "employer_contributions_jpy": employer_total,
            "investment_change_jpy": account.investment_change_jpy,
            "allocations": [{"asset_class": a.asset_class, "percentage": a.percentage} for a in allocations],
            "recent_contributions": [{"date": c.contribution_date, "employee_amount_jpy": c.employee_amount_jpy, "employer_amount_jpy": c.employer_amount_jpy} for c in contributions[:6]],
            "note": "Investment values reflect account records as of the valuation date; future returns are not guaranteed."}


def wellness_resources(db: Session, topic: str | None = None):
    query = select(WellnessResource).order_by(WellnessResource.id)
    if topic:
        query = query.where(WellnessResource.topic == topic)
    return [{"id": r.id, "title": r.title, "topic": r.topic, "description": r.description, "content": r.content} for r in db.scalars(query)]


def custody_summary(db: Session, employee_id: str):
    positions = db.scalars(select(CustodyPosition).where(CustodyPosition.employee_id == employee_id)).all()
    dividends = db.scalars(select(Dividend).where(Dividend.employee_id == employee_id).order_by(Dividend.payment_date.desc())).all()
    actions = db.scalars(select(CorporateAction).where(CorporateAction.instrument.in_([p.instrument for p in positions]))).all() if positions else []
    return {"as_of": AS_OF, "currency": "JPY",
            "positions": [{"instrument": p.instrument, "quantity": p.quantity} for p in positions],
            "dividends": [{"payment_date": d.payment_date, "instrument": d.instrument, "amount_jpy": d.amount_jpy, "status": d.status} for d in dividends],
            "corporate_actions": [{"id": a.id, "instrument": a.instrument, "title": a.title, "effective_date": a.effective_date} for a in actions]}


def equity_summary(db: Session, employee_id: str):
    grants = db.scalars(select(EquityGrant).where(EquityGrant.employee_id == employee_id).order_by(EquityGrant.grant_date.desc())).all()
    output = []
    for grant in grants:
        events = db.scalars(select(VestingEvent).where(VestingEvent.grant_id == grant.id).order_by(VestingEvent.vest_date)).all()
        vested = sum(e.units for e in events if e.status == "vested")
        output.append({"id": grant.id, "award_type": grant.award_type, "grant_date": grant.grant_date,
                       "granted_units": grant.granted_units, "vested_units": vested,
                       "unvested_units": grant.granted_units - vested,
                       "vesting_events": [{"vest_date": e.vest_date, "units": e.units, "status": e.status} for e in events]})
    upcoming = sorted((event for grant in output for event in grant["vesting_events"] if event["status"] == "scheduled" and event["vest_date"] >= AS_OF), key=lambda e: e["vest_date"])
    return {"as_of": AS_OF, "grants": output, "next_vesting": upcoming[0] if upcoming else None}


SERVICES = {"stock": stock_summary, "pension": pension_summary, "custody": custody_summary, "equity": equity_summary}
