"""Detailed read-only service views built from the original normalized records."""
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import services as base
from .models import (CorporateActionDetail, CustodyAccount, CustodySecurity,
                     CustodySettlement, CustodyValuation, Dividend, DividendDetail, EquityGrantDetail,
                     PayrollContribution, PensionContribution, PensionValuation,
                     SharePurchase, StockAccount, StockIncentive, StockPlanDetail,
                     WellnessPreference, WellnessProgress, WellnessResource)
from .seed import AS_OF


def jpy(value: Decimal):
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def growth_projection(starting_jpy: int, monthly_jpy: int, years: int, annual_return_pct: Decimal):
    """Fixed nominal annual rate and end-of-month contributions; no market prediction."""
    rate = annual_return_pct / Decimal("1200")
    value = Decimal(starting_jpy)
    for _ in range(years * 12):
        value = value * (1 + rate) + monthly_jpy
    contributed = starting_jpy + monthly_jpy * years * 12
    future = jpy(value)
    return {"starting_balance_jpy": starting_jpy, "monthly_contribution_jpy": monthly_jpy,
            "years": years, "annual_return_pct": str(annual_return_pct),
            "total_contributed_jpy": contributed, "illustrative_future_value_jpy": future,
            "illustrative_growth_jpy": future - contributed,
            "disclaimer": "Projection uses a constant return assumption. Returns are not guaranteed; this is not financial advice."}


def stock_summary(db: Session, employee_id: str):
    result = base.stock_summary(db, employee_id)
    if result is None:
        return None
    account = db.get(StockAccount, employee_id)
    plan = db.get(StockPlanDetail, employee_id)
    contributions = db.scalars(select(PayrollContribution).where(PayrollContribution.employee_id == employee_id).order_by(PayrollContribution.month.desc())).all()
    purchases = db.scalars(select(SharePurchase).where(SharePurchase.employee_id == employee_id).order_by(SharePurchase.purchase_date.desc())).all()
    incentives = db.scalars(select(StockIncentive).where(StockIncentive.employee_id == employee_id)).all()
    paid = result["total_contributions_jpy"]
    incentive_total = sum(x.amount_jpy for x in incentives)
    purchase_cost = sum(p.amount_jpy for p in purchases)
    total_cost = (plan.opening_cost_jpy if plan else 0) + purchase_cost
    shares = result["shares_held"]
    price = Decimal(plan.illustrative_price_jpy) if plan else Decimal("0")
    value = jpy(price * shares)
    activity = ([{"date": c.month, "type": "payroll_contribution", "amount_jpy": c.amount_jpy, "shares": 0} for c in contributions] +
                [{"date": p.purchase_date, "type": "share_purchase", "amount_jpy": p.amount_jpy, "shares": p.shares} for p in purchases] +
                [{"date": i.month, "type": "employer_incentive", "amount_jpy": i.amount_jpy, "shares": 0} for i in incentives])
    activity.sort(key=lambda row: (row["date"], row["type"]), reverse=True)
    purchase_items = [{"purchase_date": p.purchase_date, "shares": p.shares, "price_jpy": p.price_jpy,
                       "amount_jpy": p.amount_jpy, "status": "settled", "reference": f"BUY-{p.id:05d}"} for p in purchases]
    result.update({
        "plan_name": plan.plan_name if plan else account.plan_id,
        "enrollment_date": plan.enrollment_date if plan else None,
        "participation_status": plan.participation_status if plan else "active",
        "employer_incentive_percent": plan.employer_incentive_percent if plan else 0,
        "year_to_date_contributions_jpy": sum(c.amount_jpy for c in contributions if c.month.year == AS_OF.year),
        "employer_incentives_jpy": incentive_total,
        "uninvested_cash_jpy": paid + incentive_total - purchase_cost,
        "average_purchase_cost_jpy": str((Decimal(total_cost) / shares).quantize(Decimal("0.01"))) if shares else "0.00",
        "illustrative_share_price_jpy": str(price),
        "illustrative_portfolio_value_jpy": value,
        "illustrative_unrealized_change_jpy": value - total_cost,
        "current_quarter_purchased_shares": sum(p.shares for p in purchases if p.purchase_date.year == AS_OF.year and (p.purchase_date.month - 1) // 3 == (AS_OF.month - 1) // 3),
        "dividends_received_jpy": 0,
        "contributions": [{"month": c.month, "amount_jpy": c.amount_jpy,
                           "employer_incentive_jpy": next((x.amount_jpy for x in incentives if x.month == c.month), 0)} for c in contributions],
        "recent_purchases": purchase_items[:5], "purchases": purchase_items,
        "activity": activity,
        "statements": [{"period": str(year),
                        "employee_contributions_jpy": sum(c.amount_jpy for c in contributions if c.month.year == year),
                        "employer_incentives_jpy": sum(i.amount_jpy for i in incentives if i.month.year == year),
                        "shares_purchased": sum(p.shares for p in purchases if p.purchase_date.year == year),
                        "purchase_cost_jpy": sum(p.amount_jpy for p in purchases if p.purchase_date.year == year)}
                       for year in sorted({c.month.year for c in contributions}, reverse=True)],
        "note": "Valuations reflect the latest available account records and are not executable quotes.",
    })
    return result


def pension_summary(db: Session, employee_id: str):
    result = base.pension_summary(db, employee_id)
    if result is None:
        return None
    contributions = db.scalars(select(PensionContribution).where(PensionContribution.employee_id == employee_id).order_by(PensionContribution.contribution_date.desc())).all()
    valuations = db.scalars(select(PensionValuation).where(PensionValuation.employee_id == employee_id).order_by(PensionValuation.valuation_date.desc())).all()
    balance = result["balance_jpy"]
    monthly = (result["employee_contributions_jpy"] + result["employer_contributions_jpy"]) // len(contributions) if contributions else 0
    result.update({
        "plan_name": "Corporate Defined Contribution Plan", "enrollment_status": "active",
        "opening_balance_jpy": balance - result["employee_contributions_jpy"] - result["employer_contributions_jpy"] - result["investment_change_jpy"],
        "employer_contributions_ytd_jpy": sum(c.employer_amount_jpy for c in contributions if c.contribution_date.year == AS_OF.year),
        "illustrative_nav_change_percent": str(((Decimal(valuations[0].illustrative_nav) / Decimal(valuations[-1].illustrative_nav) - 1) * 100).quantize(Decimal("0.01"))) if len(valuations) >= 2 else "0.00",
        "equity_allocation_percent": sum(a["percentage"] for a in result["allocations"] if "equity" in a["asset_class"].lower()),
        "allocations": [{**a, "illustrative_value_jpy": jpy(Decimal(balance) * a["percentage"] / 100)} for a in result["allocations"]],
        "contribution_history": [{"date": c.contribution_date, "employee_amount_jpy": c.employee_amount_jpy,
                                  "employer_amount_jpy": c.employer_amount_jpy} for c in contributions],
        "valuation_history": [{"date": v.valuation_date, "balance_jpy": v.balance_jpy,
                               "illustrative_nav": str(v.illustrative_nav)} for v in valuations],
        "projection": growth_projection(balance, monthly, 20, Decimal("4")),
        "statements": [{"period": str(year),
                        "employee_contributions_jpy": sum(c.employee_amount_jpy for c in contributions if c.contribution_date.year == year),
                        "employer_contributions_jpy": sum(c.employer_amount_jpy for c in contributions if c.contribution_date.year == year)}
                       for year in sorted({c.contribution_date.year for c in contributions}, reverse=True)],
    })
    return result


def wellness_resources(db: Session, topic: str | None = None, search: str | None = None, employee_id: str | None = None):
    query = select(WellnessResource).order_by(WellnessResource.id)
    if topic:
        query = query.where(WellnessResource.topic == topic.lower())
    if search:
        term = f"%{search.strip()}%"
        query = query.where(WellnessResource.title.ilike(term) | WellnessResource.description.ilike(term) | WellnessResource.content.ilike(term))
    progress = {}
    if employee_id:
        progress = {p.resource_id: p.status for p in db.scalars(select(WellnessProgress).where(WellnessProgress.employee_id == employee_id))}
    return [{"id": r.id, "title": r.title, "topic": r.topic, "description": r.description,
             "content": r.content, "progress": progress.get(r.id, "not_started")} for r in db.scalars(query)]


def wellness_summary(db: Session, employee_id: str, topic: str | None = None, search: str | None = None):
    resources = wellness_resources(db, topic, search, employee_id)
    all_resources = wellness_resources(db, employee_id=employee_id)
    preference = db.get(WellnessPreference, employee_id)
    return {"as_of": AS_OF, "resources": resources,
            "topics": sorted(set(db.scalars(select(WellnessResource.topic)))),
            "preferred_topic": preference.topic if preference else None,
            "recommended_resources": wellness_resources(db, preference.topic if preference else None, employee_id=employee_id)[:3],
            "progress": {"completed": sum(r["progress"] == "completed" for r in all_resources),
                         "in_progress": sum(r["progress"] == "in_progress" for r in all_resources)},
            "note": "Educational content and deterministic calculations only; not personal financial advice."}


def custody_summary(db: Session, employee_id: str):
    account = db.get(CustodyAccount, employee_id)
    if not account:
        return None
    result = base.custody_summary(db, employee_id)
    positions = []
    for row in result["positions"]:
        security = db.get(CustodySecurity, row["instrument"])
        price = Decimal(security.illustrative_price_jpy) if security else Decimal("0")
        positions.append({**row, "security_id": security.security_id if security else "",
                          "asset_class": security.asset_class if security else "unknown",
                          "illustrative_price_jpy": str(price),
                          "illustrative_value_jpy": jpy(price * row["quantity"])})
    dividends = []
    for row in result["dividends"]:
        dividend = db.scalar(select(Dividend).where(Dividend.employee_id == employee_id,
                                                   Dividend.payment_date == row["payment_date"],
                                                   Dividend.instrument == row["instrument"]))
        detail = db.get(DividendDetail, dividend.id) if dividend else None
        dividends.append({**row, "record_date": detail.record_date if detail else None})
    actions = []
    for row in result["corporate_actions"]:
        detail = db.get(CorporateActionDetail, row["id"])
        actions.append({**row, "record_date": detail.record_date if detail else None,
                        "status": detail.status if detail else "unknown"})
    settlements = db.scalars(select(CustodySettlement).where(CustodySettlement.employee_id == employee_id).order_by(CustodySettlement.trade_date.desc())).all()
    valuations = db.scalars(select(CustodyValuation).where(CustodyValuation.employee_id == employee_id).order_by(CustodyValuation.valuation_date.desc())).all()
    result.update({"account_id": account.account_id, "account_status": account.account_status,
                   "opened_on": account.opened_on, "positions": positions, "dividends": dividends,
                   "corporate_actions": actions,
                   "illustrative_portfolio_value_jpy": sum(p["illustrative_value_jpy"] for p in positions),
                   "dividends_received_ytd_jpy": sum(d["amount_jpy"] for d in dividends if d["status"] == "credited" and d["payment_date"].year == AS_OF.year),
                   "pending_corporate_actions": sum(a["status"] == "announced" for a in actions),
                   "settlements": [{"id": s.id, "instrument": s.instrument, "trade_date": s.trade_date,
                                    "settlement_date": s.settlement_date, "quantity": s.quantity, "status": s.status} for s in settlements],
                   "valuation_history": [{"date": v.valuation_date, "illustrative_value_jpy": v.illustrative_value_jpy} for v in valuations],
                   "statements": [{"period": "2026", "dividends_credited_jpy": sum(d["amount_jpy"] for d in dividends if d["status"] == "credited" and d["payment_date"].year == 2026),
                                   "settled_events": sum(s.status == "settled" for s in settlements)}],
                   "note": "Valuations and settlements are read-only account records. Contact the custody team for account instructions."})
    return result


def equity_summary(db: Session, employee_id: str):
    result = base.equity_summary(db, employee_id)
    grants = []
    for grant in result["grants"]:
        detail = db.get(EquityGrantDetail, grant["id"])
        vested = grant["vested_units"]
        scheduled = sum(e["units"] for e in grant["vesting_events"] if e["status"] == "scheduled")
        forfeited = detail.forfeited_units if detail else 0
        if vested + scheduled + forfeited != grant["granted_units"]:
            raise ValueError(f"Grant {grant['id']} quantities do not reconcile")
        price = Decimal(detail.illustrative_share_price_jpy) if detail else Decimal("0")
        strike = Decimal(detail.exercise_price_jpy) if detail and detail.exercise_price_jpy is not None else None
        exercised = detail.exercised_units if detail else 0
        eligible = max(vested - exercised, 0) if grant["award_type"] == "Option" else 0
        grants.append({**grant, "unvested_units": scheduled,
                       "plan_name": detail.plan_name if detail else "Equity Awards Plan",
                       "vesting_condition": detail.vesting_condition if detail else "Plan conditions apply",
                       "forfeited_units": forfeited, "released_units": detail.released_units if detail else 0,
                       "exercised_units": exercised, "exercise_eligible_units": eligible,
                       "exercise_price_jpy": str(strike) if strike is not None else None,
                       "expiry_date": detail.expiry_date if detail else None,
                       "illustrative_share_price_jpy": str(price),
                       "illustrative_award_value_jpy": jpy(max(price - strike, Decimal("0")) * eligible if strike is not None else price * (scheduled + vested))})
    result.update({"grants": grants,
                   "summary": {"grant_count": len(grants), "vested_units": sum(g["vested_units"] for g in grants),
                               "unvested_units": sum(g["unvested_units"] for g in grants),
                               "exercise_eligible_options": sum(g["exercise_eligible_units"] for g in grants)},
                   "statements": [{"grant_id": g["id"], "grant_date": g["grant_date"], "award_type": g["award_type"],
                                   "granted_units": g["granted_units"], "vested_units": g["vested_units"]} for g in grants],
                   "note": "Vesting is distinct from release, exercise, and sale. Award values are based on the latest available price."})
    return result


SERVICES = {"stock": stock_summary, "pension": pension_summary,
            "custody": custody_summary, "equity": equity_summary}
