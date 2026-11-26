"""Reproducible synthetic records. No real employee or bank records."""
from sqlalchemy import select
from .database import Base, engine, SessionLocal
from .models import Tenant, Employee, ServicePermission, EmployeeService, WellnessResource, WellnessProgress

SERVICES = {
  "stock-ownership": {"title":"Employee Stock Ownership","subtitle":"Payroll deductions, purchases and accumulated shares","tools":["get_stock_ownership_summary","get_stock_purchase_history"]},
  "pension": {"title":"Corporate Pension","subtitle":"Corporate DC balances, contributions and fund allocations","tools":["get_pension_summary","get_pension_allocation"]},
  "wellness": {"title":"Financial Wellness","subtitle":"Financial education, calculators and resource progress","tools":["search_financial_wellness","get_wellness_progress"]},
  "custody": {"title":"Trust & Custody","subtitle":"Held positions, dividends and corporate-action notices","tools":["get_custody_summary","get_corporate_actions"]},
  "equity-compensation": {"title":"Equity Compensation","subtitle":"RSU and option grants, vesting and award events","tools":["get_equity_awards","get_vesting_schedule"]},
}

def stock_record(employee: str, months: list[tuple[int,int]], employee_amount: int, shares_each: int, price: int, incentive_pct: int):
    contributions=[]; purchases=[]
    for y,m in months:
        benefit=employee_amount*incentive_pct//100
        assert (shares_each*price)==employee_amount+benefit
        date=f"{y}-{m:02d}-05"
        contributions.append({"period":f"{y}-{m:02d}","date":date,"employee_jpy":employee_amount,"employer_jpy":benefit,"total_jpy":employee_amount+benefit,"status":"POSTED"})
        purchases.append({"id":f"BUY-{employee}-{y}{m:02d}","date":f"{y}-{m:02d}-10","shares":shares_each,"price_jpy":price,"amount_jpy":shares_each*price,"status":"SETTLED"})
    return {"plan":{"id":"SHP-001","name":"Employee Shareholding Association · Demo","symbol":"DEMO-7203","currency":"JPY","enrollment_date":f"{months[0][0]}-{months[0][1]:02d}-01","employee_contribution_jpy":employee_amount,"employer_incentive_pct":incentive_pct},"contributions":contributions,"purchases":purchases,"illustrative_price_jpy":price+120,"as_of":"2026-11-26"}

def pension_record(bal, opening, employee_monthly, employer_monthly, allocations, joined=2026):
    contributions=[{"date":f"2026-{m:02d}-25","employee_jpy":employee_monthly,"employer_jpy":employer_monthly,"status":"POSTED"} for m in range(1,12)]
    paid=sum((x["employee_jpy"]+x["employer_jpy"]) for x in contributions)
    gain=bal-opening-paid
    assert sum(a["percent"] for a in allocations)==100
    return {"account":{"id":"PEN-DEMO","plan_name":"Corporate Defined Contribution Plan · Demo","plan_type":"CORPORATE_DC","currency":"JPY","opening_balance_jpy":opening,"current_balance_jpy":bal,"investment_change_jpy":gain,"as_of":"2026-11-26"},"contributions":contributions,"allocations":allocations,"projection":{"default_annual_return_pct":4,"years":20,"disclaimer":"Illustrative compound growth only; not a forecast, guarantee, or investment recommendation."}}

def custody_record(employee, qty):
    return {"account":{"id":f"CUST-{employee}","account_type":"SYNTHETIC_CUSTODY","currency":"JPY","as_of":"2026-11-26"},"positions":[{"isin":"DEMO-ISIN-01","instrument":"Demo Domestic Equity Basket","asset_class":"EQUITY","quantity":qty,"unit_price_jpy":1820,"currency":"JPY","as_of":"2026-11-26"},{"isin":"DEMO-ISIN-02","instrument":"Demo Government Bond Basket","asset_class":"FIXED_INCOME","quantity":10,"unit_price_jpy":10000,"currency":"JPY","as_of":"2026-11-26"}],"dividends":[{"id":f"DIV-{employee}-1","security":"Demo Domestic Equity Basket","record_date":"2026-06-30","payment_date":"2026-07-25","amount_jpy":qty*24,"status":"PAID"},{"id":f"DIV-{employee}-2","security":"Demo Domestic Equity Basket","record_date":"2026-12-31","payment_date":"2027-01-26","amount_jpy":qty*24,"status":"ANNOUNCED"}],"corporate_actions":[{"id":"CA-001","security":"Demo Domestic Equity Basket","type":"CASH_DIVIDEND","description":"Illustrative year-end distribution","record_date":"2026-12-31","effective_date":"2027-01-26","status":"ANNOUNCED"},{"id":"CA-002","security":"Demo Government Bond Basket","type":"INTEREST_PAYMENT","description":"Illustrative coupon event","record_date":"2026-10-15","effective_date":"2026-10-17","status":"COMPLETED"}],"settlements":[{"id":f"SET-{employee}-1","instrument":"Demo Government Bond Basket","trade_date":"2026-10-12","settlement_date":"2026-10-14","quantity":10,"status":"SETTLED"}]}

def equity_record(employee, with_options=True):
    grants=[{"id":f"RSU-{employee}-2025","type":"RSU","grant_date":"2025-06-10","units_granted":400,"units_forfeited":0,"units_released":0,"status":"ACTIVE","vesting":[{"date":"2026-06-10","units":100,"status":"VESTED"},{"date":"2027-06-10","units":100,"status":"SCHEDULED"},{"date":"2028-06-10","units":100,"status":"SCHEDULED"},{"date":"2029-06-10","units":100,"status":"SCHEDULED"}]}]
    if with_options:
        grants.append({"id":f"OPT-{employee}-2025","type":"STOCK_OPTION","grant_date":"2025-03-01","units_granted":200,"units_forfeited":0,"units_exercised":0,"exercise_price_jpy":2240,"expiry_date":"2035-03-01","status":"ACTIVE","vesting":[{"date":"2026-03-01","units":100,"status":"VESTED"},{"date":"2027-03-01","units":100,"status":"SCHEDULED"}]})
    return {"plan":{"name":"Synthetic Equity Awards Plan","currency":"JPY","as_of":"2026-11-26","illustrative_share_price_jpy":2680},"grants":grants}

RESOURCES=[
 ("W-001","Retirement","Understanding corporate DC pensions","A plain-language guide to corporate defined-contribution accounts, employee contributions, employer contributions, and investment risk.","A corporate defined-contribution pension account receives contributions that are invested according to the applicable plan options. Future value depends on contributions, investment returns, fees, and market conditions. Example values in this demonstration are synthetic.",6,"Foundations"),
 ("W-002","Shareholding","Employee shareholding vs equity awards","How payroll-based shareholding plans differ from RSU and stock-option compensation.","Employee shareholding generally uses payroll deductions to accumulate company shares. Equity awards such as RSUs and options are employer-issued compensation with separate grant, vesting, and release or exercise rules.",5,"Foundations"),
 ("W-003","Budgeting","Creating a monthly savings plan","Learn to set a savings goal and reserve a predictable amount every month.","A savings plan starts with income, essential expenses, an emergency buffer, and a chosen monthly contribution. Revisit it when your circumstances change. The calculator in this POC illustrates arithmetic, not an investment recommendation.",4,"Foundations"),
 ("W-004","Investing","Diversification and risk","Understand why spreading investments does not eliminate risk.","Different assets have different risk and return characteristics. Diversification can reduce concentration risk but cannot eliminate market losses. Investment decisions should consider objectives, constraints, and risk tolerance.",7,"Intermediate"),
 ("W-005","Retirement","Understanding contribution matching","How employer incentives may affect retirement-plan contributions.","Employer contributions vary by plan rules. A matching contribution is separate from employee contributions and may have eligibility or vesting conditions. Always consult actual plan documents.",4,"Foundations"),
 ("W-006","Shareholding","Reading a share purchase statement","Find quantity, execution date, purchase cost and credited units.","A share purchase statement may show contribution dates, shares purchased, price, fees and credited quantity. Holdings are not the same as the invested principal, because market prices can fluctuate.",5,"Intermediate"),
 ("W-007","Custody","Corporate actions explained","Dividends, splits, record dates and payment dates.","Corporate actions can affect security holdings or cash distributions. An announced payment is not the same as a completed payment. Check record date, payment date and the provider's processing status.",6,"Foundations"),
 ("W-008","Equity","What does vesting mean?","Understand how grant dates, vesting schedules and exercise differ.","Vesting determines when particular awards become eligible under plan rules. Vesting does not automatically mean sale, share release, option exercise or cash transfer. Tax consequences may apply.",5,"Foundations"),
]

def seed_database(reset: bool = False):
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Tenant.id).limit(1)):
            return False
        db.add_all([Tenant(id="toyota-demo",name="Toyota · Hypothetical Demo Client",mcp_enabled=True,updated_by="seed"),Tenant(id="harbor-demo",name="Harbor Works · Fictional Test Client",mcp_enabled=True,updated_by="seed")])
        db.flush()
        employee_defs=[("TYO-001","toyota-demo","Aiko Mori","Operations","Planning Specialist","2023-04-01"),("TYO-002","toyota-demo","Kenji Takeda","Engineering","Technical Coordinator","2024-07-01"),("TYO-003","toyota-demo","Mina Watanabe","People Operations","HR Associate","2026-01-10"),("HBR-001","harbor-demo","Rina Hayashi","Finance","Analyst","2022-08-01")]
        db.add_all([Employee(id=i,tenant_id=t,display_name=n,department=d,job_title=j,joined_on=since,status="ACTIVE") for i,t,n,d,j,since in employee_defs])
        db.flush()
        for tid in ("toyota-demo","harbor-demo"):
            for service in SERVICES:
                db.add(ServicePermission(tenant_id=tid, service_key=service, enabled=True, updated_by="seed"))
        months=[(y,m) for y,m in [(2025,m) for m in range(7,13)]+[(2026,m) for m in range(1,12)]]
        records={
          "TYO-001":{
             "stock-ownership":stock_record("TYO-001",months,20000,7,3000,5),
             "pension":pension_record(5250000,4618000,25000,25000,[{"fund":"Domestic equity index","asset_class":"Equities","percent":40},{"fund":"Global bond index","asset_class":"Fixed income","percent":35},{"fund":"Balanced fund","asset_class":"Multi-asset","percent":25}]),
             "custody":custody_record("TYO-001",150),
             "equity-compensation":equity_record("TYO-001"),
          },
          "TYO-002":{
             "stock-ownership":stock_record("TYO-002",[(2026,m) for m in range(4,12)],10000,5,2000,0),
             "pension":pension_record(2120000,1790000,15000,15000,[{"fund":"Balanced fund","asset_class":"Multi-asset","percent":50},{"fund":"Global equity index","asset_class":"Equities","percent":35},{"fund":"Cash-like fund","asset_class":"Cash","percent":15}]),
             "custody":custody_record("TYO-002",40),
             "equity-compensation":equity_record("TYO-002",False)
          },
          "TYO-003":{
             "pension":pension_record(792000,672000,6000,6000,[{"fund":"Balanced fund","asset_class":"Multi-asset","percent":100}]),
          },
          "HBR-001":{
             "stock-ownership":stock_record("HBR-001",[(2026,m) for m in range(1,12)],10000,5,2000,0),
             "pension":pension_record(2300000,1970000,15000,15000,[{"fund":"Balanced fund","asset_class":"Multi-asset","percent":100}]),
             "custody":custody_record("HBR-001",65),
             "equity-compensation":equity_record("HBR-001",False),
          }
        }
        for employee_id, entry in records.items():
            for service_key, payload in entry.items():
                db.add(EmployeeService(employee_id=employee_id,service_key=service_key,payload=payload))
        db.add_all([WellnessResource(id=i,topic=t,title=title,summary=summary,body=body,reading_minutes=mins,level=level) for i,t,title,summary,body,mins,level in RESOURCES])
        db.flush()
        db.add_all([WellnessProgress(employee_id="TYO-001",resource_id="W-001",status="completed"),WellnessProgress(employee_id="TYO-001",resource_id="W-002",status="in_progress"),WellnessProgress(employee_id="TYO-002",resource_id="W-003",status="completed")])
        db.commit()
    return True

if __name__ == "__main__":
    print("Database seeded." if seed_database() else "Database already seeded; no changes made.")
