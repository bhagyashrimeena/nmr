"""Authoritative mock-domain calculations; no LLM decisions or financial execution."""
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import EmployeeService, WellnessResource, WellnessProgress

AS_OF = "2026-11-26"

def lookup_payload(db: Session, employee_id: str, service: str) -> dict | None:
    record = db.scalar(select(EmployeeService).where(EmployeeService.employee_id==employee_id, EmployeeService.service_key==service))
    return record.payload if record else None

def stock_ownership(payload: dict | None, employee_id: str) -> dict:
    if not payload:
        return {"service":"stock-ownership","employee_id":employee_id,"enrolled":False,"message":"No active employee shareholding membership for this employee.","as_of":AS_OF}
    purchases=payload["purchases"]
    contribs=payload["contributions"]
    shares=sum(Decimal(str(p["shares"])) for p in purchases if p["status"]=="SETTLED")
    paid=sum(c["employee_jpy"] for c in contribs if c["status"]=="POSTED")
    benefits=sum(c["employer_jpy"] for c in contribs if c["status"]=="POSTED")
    spent=sum(p["amount_jpy"] for p in purchases if p["status"]=="SETTLED")
    cash=paid+benefits-spent
    year_to_date=sum(c["employee_jpy"] for c in contribs if c["period"].startswith("2026"))
    price=payload["illustrative_price_jpy"]
    return {"service":"stock-ownership","employee_id":employee_id,"enrolled":True,"as_of":payload["as_of"],"currency":"JPY","plan":payload["plan"],"summary":{"shares_held":float(shares),"employee_contributions_jpy":paid,"employer_incentives_jpy":benefits,"contributions_2026_jpy":year_to_date,"total_purchases_jpy":spent,"uninvested_cash_jpy":cash,"illustrative_unit_price_jpy":price,"illustrative_market_value_jpy":int(shares*price),"purchase_count":len(purchases)},"contributions":sorted(contribs,key=lambda x:x["date"],reverse=True),"purchases":sorted(purchases,key=lambda x:x["date"],reverse=True),"disclaimer":"Illustrative shareholding plan, prices and performance; all values synthetic."}

def pension(payload: dict | None, employee_id: str, annual_return_pct: float=4.0, years: int=20) -> dict:
    if not payload:
        return {"service":"pension","employee_id":employee_id,"enrolled":False,"message":"No corporate pension account for this employee.","as_of":AS_OF}
    contributions=payload["contributions"]
    paid_employee=sum(row["employee_jpy"] for row in contributions)
    paid_employer=sum(row["employer_jpy"] for row in contributions)
    acct=payload["account"]
    assert sum(row["percent"] for row in payload["allocations"])==100
    monthly=Decimal(str((paid_employee+paid_employer)/len(contributions))) if contributions else Decimal(0)
    rate=Decimal(str(annual_return_pct))/Decimal(1200)
    fv=Decimal(acct["current_balance_jpy"])
    for _ in range(years*12):
        fv=fv*(1+rate)+monthly
    amount=int(fv.quantize(Decimal("1"),rounding=ROUND_HALF_UP))
    return {"service":"pension","employee_id":employee_id,"enrolled":True,"currency":"JPY","as_of":acct["as_of"],"account":acct,"summary":{"current_balance_jpy":acct["current_balance_jpy"],"employee_contributions_2026_jpy":paid_employee,"employer_contributions_2026_jpy":paid_employer,"total_contributions_2026_jpy":paid_employee+paid_employer,"investment_change_2026_jpy":acct["investment_change_jpy"],"monthly_combined_contribution_jpy":int(monthly)},"allocations":[{**a,"illustrative_value_jpy":int(acct["current_balance_jpy"]*a["percent"]/100)} for a in payload["allocations"]],"contributions":sorted(contributions,key=lambda x:x["date"],reverse=True),"projection":{"years":years,"annual_return_pct":annual_return_pct,"monthly_contribution_jpy":int(monthly),"illustrative_future_balance_jpy":amount,"disclaimer":payload["projection"]["disclaimer"]}}

def custody(payload: dict | None, employee_id: str) -> dict:
    if not payload:
        return {"service":"custody","employee_id":employee_id,"enrolled":False,"message":"No synthetic custody account for this employee.","as_of":AS_OF}
    positions=payload["positions"]
    positions=[{**p,"illustrative_value_jpy":int(Decimal(str(p["quantity"]))*Decimal(str(p["unit_price_jpy"]))) } for p in positions]
    return {"service":"custody","employee_id":employee_id,"enrolled":True,"as_of":payload["account"]["as_of"],"currency":"JPY","account":payload["account"],"summary":{"positions_count":len(positions),"illustrative_portfolio_value_jpy":sum(p["illustrative_value_jpy"] for p in positions),"paid_dividends_jpy":sum(d["amount_jpy"] for d in payload["dividends"] if d["status"]=="PAID"),"pending_corporate_actions":sum(1 for a in payload["corporate_actions"] if a["status"]=="ANNOUNCED")},"positions":positions,"dividends":payload["dividends"],"corporate_actions":payload["corporate_actions"],"settlements":payload["settlements"],"disclaimer":"Synthetic custody and asset-servicing history; no live deposits, settlements or dividend processing."}

def equity_compensation(payload: dict | None, employee_id: str) -> dict:
    if not payload:
        return {"service":"equity-compensation","employee_id":employee_id,"enrolled":False,"message":"No equity awards issued for this employee in the demo.","as_of":AS_OF,"grants":[]}
    enriched=[]
    for grant in payload["grants"]:
        vested=sum(ev["units"] for ev in grant["vesting"] if ev["status"]=="VESTED")
        scheduled=sum(ev["units"] for ev in grant["vesting"] if ev["status"]=="SCHEDULED")
        total=vested+scheduled+grant["units_forfeited"]
        if total!=grant["units_granted"]:
            raise ValueError(f"Invalid seed grant {grant['id']}: quantities do not reconcile")
        next_events=[ev for ev in grant["vesting"] if ev["status"]=="SCHEDULED"]
        enriched.append({**grant,"units_vested":vested,"units_unvested":scheduled,"next_vesting_date":min((ev["date"] for ev in next_events), default=None),"illustrative_granted_value_jpy":grant["units_granted"]*payload["plan"]["illustrative_share_price_jpy"]})
    return {"service":"equity-compensation","employee_id":employee_id,"enrolled":True,"currency":"JPY","as_of":payload["plan"]["as_of"],"plan":payload["plan"],"summary":{"grant_count":len(enriched),"units_granted":sum(g["units_granted"] for g in enriched),"units_vested":sum(g["units_vested"] for g in enriched),"units_unvested":sum(g["units_unvested"] for g in enriched),"next_vesting_date":min((g["next_vesting_date"] for g in enriched if g["next_vesting_date"]),default=None)},"grants":enriched,"disclaimer":"Synthetic grants, vesting and option eligibility; there is no exercise, release or sale capability."}

def wellness(db: Session, employee_id: str, topic: str | None = None):
    stmt=select(WellnessResource)
    if topic and topic.lower()!="all":
        stmt=stmt.where(WellnessResource.topic.ilike(f"%{topic}%"))
    resources=db.scalars(stmt.order_by(WellnessResource.topic,WellnessResource.id)).all()
    progress={p.resource_id:p.status for p in db.scalars(select(WellnessProgress).where(WellnessProgress.employee_id==employee_id)).all()}
    return {"service":"wellness","employee_id":employee_id,"as_of":AS_OF,"resources":[{"id":r.id,"title":r.title,"topic":r.topic,"summary":r.summary,"body":r.body,"reading_minutes":r.reading_minutes,"level":r.level,"progress":progress.get(r.id,"not_started")} for r in resources],"topics":["Retirement","Shareholding","Budgeting","Investing","Custody","Equity"],"summary":{"resource_count":len(resources),"completed_count":sum(1 for r in resources if progress.get(r.id)=="completed"),"in_progress_count":sum(1 for r in resources if progress.get(r.id)=="in_progress")},"disclaimer":"Educational material only; not personalized financial or investment advice."}

def get_service(db:Session, service_key:str, employee_id:str, topic:str|None=None, annual_return_pct:float=4.0, years:int=20):
    if service_key=="wellness":
        return wellness(db,employee_id,topic=topic)
    payload=lookup_payload(db,employee_id,service_key)
    if service_key=="stock-ownership": return stock_ownership(payload,employee_id)
    if service_key=="pension": return pension(payload,employee_id,annual_return_pct=annual_return_pct,years=years)
    if service_key=="custody": return custody(payload,employee_id)
    if service_key=="equity-compensation": return equity_compensation(payload,employee_id)
    raise KeyError(service_key)

def savings_projection(monthly_jpy: int, years: int, annual_return_pct: float):
    """Simple monthly contribution growth; educational illustration, not advice."""
    monthly=Decimal(monthly_jpy)
    rate=Decimal(str(annual_return_pct))/Decimal(1200)
    total=Decimal(0)
    for _ in range(years*12):
        total=total*(1+rate)+monthly
    contributions=monthly*years*12
    future=int(total.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    return {"service":"wellness","calculator":"MONTHLY_SAVINGS","inputs":{"monthly_jpy":monthly_jpy,"years":years,"annual_return_pct":annual_return_pct},"illustrative_future_value_jpy":future,"total_contributions_jpy":int(contributions),"illustrative_growth_jpy":future-int(contributions),"disclaimer":"Educational arithmetic using a fixed hypothetical rate. No guarantee of returns; not personalized investment advice."}
