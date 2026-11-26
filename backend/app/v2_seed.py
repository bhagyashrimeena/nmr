"""Additive, repeatable operational fixtures for the v2 shareholding ledger."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Employee, PayrollContribution, SharePurchase, StockAccount, StockIncentive, StockPlanDetail, Tenant
from .v2_models import (
    ContributionElection, EmployeeProfile, FinancialEvent, LegalEntity, OperationalStatement,
    ParticipantOperationalProfile,
    ReconciliationCase, ShareMembership, SharePayrollBatch, SharePayrollLine, SharePayrollRuleLink,
    SharePurchaseAllocation, SharePurchaseCycle, ShareTransferRequest, ShareholdingPlan,
    ShareholdingRuleVersion, TenantOperationalStatus,
    WorkflowTask, WorkflowTransition,
)

SNAPSHOT = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def at_day(value):
    return datetime(value.year, value.month, value.day, 12, 0, tzinfo=timezone.utc)


def add_event(db: Session, *, event_id: str, tenant_id: str, employee_id: str | None,
              event_type: str, source: str, when: datetime, amount: Decimal = Decimal("0"),
              quantity: Decimal = Decimal("0"), actor: str = "nmr-operations",
              correlation_id: str | None = None):
    if db.get(FinancialEvent, event_id):
        return
    db.add(FinancialEvent(id=event_id, tenant_id=tenant_id, employee_id=employee_id,
                          service="stock", event_type=event_type, source_reference=source,
                          idempotency_key=event_id, correlation_id=correlation_id,
                          occurred_at=when, effective_at=when, recorded_at=SNAPSHOT,
                          amount_jpy=amount, quantity=quantity, actor=actor))


def seed_v2(db: Session):
    entities = {
        "toyota-demo": ("LE-TOYOTA", "Toyota Motor Corporation", "TOYOTA-SHARE-01", "Toyota Employee Shareholding Association", "Toyota Motor"),
        "secondary-demo": ("LE-SAKURA", "Sakura Mobility Co., Ltd.", "SAKURA-SHARE-01", "Sakura Employee Share Plan", "Sakura Mobility"),
        "asterfield": ("LE-AST", "Asterfield Industries Ltd.", "ASTER-SHARE-01", "Asterfield Employee Shareholding Association", "Asterfield Industries"),
    }
    for tenant_id, (entity_id, name, plan_id, plan_name, issuer) in entities.items():
        if not db.get(Tenant, tenant_id):
            continue
        if not db.get(TenantOperationalStatus, tenant_id):
            db.add(TenantOperationalStatus(tenant_id=tenant_id, status="ACTIVE"))
        if not db.get(LegalEntity, entity_id):
            db.add(LegalEntity(id=entity_id, tenant_id=tenant_id, name=name))
        plan_row = db.get(ShareholdingPlan, plan_id)
        if not plan_row:
            plan_row = ShareholdingPlan(id=plan_id, tenant_id=tenant_id, legal_entity_id=entity_id,
                                    name=plan_name, issuer=issuer,
                                    minimum_monthly_jpy=Decimal("1000"), maximum_monthly_jpy=Decimal("100000"),
                                    incentive_percent=Decimal("5") if tenant_id == "toyota-demo" else Decimal("0"),
                                    fractional_units_allowed=tenant_id == "toyota-demo", minimum_transfer_units=Decimal("1"),
                                    next_purchase_date=date(2026, 12, 1), status="ACTIVE")
            db.add(plan_row)
        elif plan_row.next_purchase_date == date(2026, 11, 1):
            plan_row.next_purchase_date = date(2026, 12, 1)
        if tenant_id == "toyota-demo":
            plan_row.fractional_units_allowed = True
        rule_id = f"RULE-{plan_id}-2026"
        if not db.get(ShareholdingRuleVersion, rule_id):
            db.add(ShareholdingRuleVersion(id=rule_id, plan_id=plan_id,
                                           effective_on=date(2026, 1, 1),
                                           source_reference=f"{plan_id}/RULES/2026",
                                           incentive_percent=Decimal("5") if tenant_id == "toyota-demo" else Decimal("0"),
                                           minimum_transfer_units=Decimal("1"),
                                           fractional_beneficial_units=tenant_id == "toyota-demo"))
        for employee in db.scalars(select(Employee).where(Employee.tenant_id == tenant_id)):
            if not db.get(EmployeeProfile, employee.id):
                operational = db.get(ParticipantOperationalProfile, employee.id)
                db.add(EmployeeProfile(employee_id=employee.id, legal_entity_id=entity_id,
                                       hired_on=operational.hired_on if operational else SNAPSHOT.date().replace(year=2022),
                                       left_on=operational.left_on if operational else None,
                                       employment_status="ACTIVE" if employee.active else "LEFT"))
    db.flush()

    for account in db.scalars(select(StockAccount).order_by(StockAccount.employee_id)):
        employee = db.get(Employee, account.employee_id)
        detail = db.get(StockPlanDetail, account.employee_id)
        membership_id = f"MEM-{account.employee_id}"
        if not db.get(ShareMembership, membership_id):
            db.add(ShareMembership(id=membership_id, plan_id=account.plan_id, employee_id=account.employee_id,
                                   joined_on=detail.enrollment_date, status="ACTIVE" if employee.active else "LEFT",
                                   opening_units=Decimal(account.opening_shares), opening_cash_jpy=Decimal("0")))
        if not db.get(ContributionElection, f"ELECT-{account.employee_id}"):
            db.add(ContributionElection(id=f"ELECT-{account.employee_id}", membership_id=membership_id,
                                        monthly_jpy=Decimal(account.monthly_contribution_jpy),
                                        effective_period=detail.enrollment_date.replace(day=1), state="EFFECTIVE"))
        add_event(db, event_id=f"EV-OPEN-{account.employee_id}", tenant_id=employee.tenant_id,
                  employee_id=account.employee_id, event_type="OPENING_UNITS",
                  source=membership_id, when=at_day(detail.enrollment_date),
                  quantity=Decimal(account.opening_shares))
    db.flush()

    incentive_by_employee_month = {
        (row.employee_id, row.month): row.amount_jpy for row in db.scalars(select(StockIncentive))
    }
    for contribution in db.scalars(select(PayrollContribution).order_by(PayrollContribution.id)):
        employee = db.get(Employee, contribution.employee_id)
        plan = db.get(StockAccount, contribution.employee_id)
        period = contribution.month
        batch_id = f"PAY-{contribution.employee_id}-{period:%Y%m}"
        incentive = incentive_by_employee_month.get((contribution.employee_id, period), 0)
        if not db.get(SharePayrollBatch, batch_id):
            db.add(SharePayrollBatch(id=batch_id, plan_id=plan.plan_id, period=period,
                                     source_reference=batch_id, expected_jpy=Decimal(contribution.amount_jpy),
                                     received_jpy=Decimal(contribution.amount_jpy), state="POSTED"))
            db.add(SharePayrollLine(id=f"LINE-{batch_id}", batch_id=batch_id,
                                    employee_id=contribution.employee_id,
                                    amount_jpy=Decimal(contribution.amount_jpy),
                                    incentive_jpy=Decimal(incentive), state="POSTED"))
        if period >= date(2026, 1, 1) and not db.get(SharePayrollRuleLink, batch_id):
            db.add(SharePayrollRuleLink(batch_id=batch_id, rule_id=f"RULE-{plan.plan_id}-2026"))
        add_event(db, event_id=f"EV-CASH-{batch_id}", tenant_id=employee.tenant_id,
                  employee_id=contribution.employee_id, event_type="PAYROLL_POSTED",
                  source=batch_id, when=at_day(period), amount=Decimal(contribution.amount_jpy))
        if incentive:
            add_event(db, event_id=f"EV-INC-{batch_id}", tenant_id=employee.tenant_id,
                      employee_id=contribution.employee_id, event_type="INCENTIVE_POSTED",
                      source=batch_id, when=at_day(period), amount=Decimal(incentive))

    for purchase in db.scalars(select(SharePurchase).order_by(SharePurchase.id)):
        employee = db.get(Employee, purchase.employee_id)
        plan = db.get(StockAccount, purchase.employee_id)
        cycle_id = f"BUY-{purchase.id:05d}"
        if not db.get(SharePurchaseCycle, cycle_id):
            db.add(SharePurchaseCycle(id=cycle_id, plan_id=plan.plan_id, source_reference=cycle_id,
                                      trade_date=purchase.purchase_date,
                                      settlement_date=purchase.purchase_date,
                                      unit_price_jpy=Decimal(purchase.price_jpy),
                                      acquired_units=Decimal(purchase.shares), state="ALLOCATED"))
            db.add(SharePurchaseAllocation(id=f"ALLOC-{cycle_id}", cycle_id=cycle_id,
                                           employee_id=purchase.employee_id,
                                           units=Decimal(purchase.shares),
                                           cost_jpy=Decimal(purchase.amount_jpy), state="ALLOCATED"))
        add_event(db, event_id=f"EV-ALLOC-{cycle_id}", tenant_id=employee.tenant_id,
                  employee_id=purchase.employee_id, event_type="PURCHASE_ALLOCATED",
                  source=cycle_id, when=at_day(purchase.purchase_date),
                  amount=-Decimal(purchase.amount_jpy), quantity=Decimal(purchase.shares))

    # The rejected line has no cash or unit journal entry and therefore cannot alter holdings.
    rejected_id = "PAY-EMP-002-202611"
    if not db.get(SharePayrollBatch, rejected_id):
        db.add(SharePayrollBatch(id=rejected_id, plan_id="TOYOTA-SHARE-01",
                                 period=SNAPSHOT.date().replace(day=1), source_reference=rejected_id,
                                 expected_jpy=Decimal("10000"), received_jpy=Decimal("0"),
                                 state="REJECTED"))
        db.add(SharePayrollLine(id=f"LINE-{rejected_id}", batch_id=rejected_id,
                                employee_id="EMP-002", amount_jpy=Decimal("10000"),
                                incentive_jpy=Decimal("0"), state="REJECTED",
                                rejection_reason="Employee payroll reference did not match the plan roster"))
    elif db.get(SharePayrollBatch, rejected_id).state == "PARTIALLY_REJECTED":
        db.get(SharePayrollBatch, rejected_id).state = "REJECTED"
    if not db.get(ReconciliationCase, "BREAK-STOCK-001"):
        db.add(ReconciliationCase(id="BREAK-STOCK-001", tenant_id="toyota-demo",
                                  service="stock", employee_id="EMP-002",
                                  source_reference=rejected_id, break_type="UNMATCHED_PAYROLL",
                                  expected_jpy=Decimal("10000"), actual_jpy=Decimal("0"),
                                  status="OPEN", owner="Payroll reconciliation"))
    if not db.get(WorkflowTask, "TASK-STOCK-001"):
        db.add(WorkflowTask(id="TASK-STOCK-001", tenant_id="toyota-demo", service="stock",
                            employee_id="EMP-002", operation_key="payroll_exception",
                            resource_id="BREAK-STOCK-001", state="OPEN",
                            reviewer_role="payroll_operator", evidence_reference=rejected_id,
                            created_at=SNAPSHOT, updated_at=SNAPSHOT))
        db.add(WorkflowTransition(task_id="TASK-STOCK-001", from_state=None, to_state="OPEN",
                                  actor="nmr-operations", reason="Payroll line rejected for roster mismatch",
                                  occurred_at=SNAPSHOT))
    if not db.get(ShareTransferRequest, "TR-001"):
        db.add(ShareTransferRequest(id="TR-001", tenant_id="toyota-demo", employee_id="EMP-002",
                                    plan_id="TOYOTA-SHARE-01", units=Decimal("2"),
                                    recipient_account_reference="CUST-EMP-002", state="REQUESTED",
                                    idempotency_key="seed-transfer-001", correlation_id="TR-001",
                                    submitted_at=SNAPSHOT))
        db.add(WorkflowTask(id="TASK-TR-001", tenant_id="toyota-demo", service="stock",
                            employee_id="EMP-002", operation_key="share_transfer",
                            resource_id="TR-001", state="REQUESTED",
                            reviewer_role="plan_operator", evidence_reference="CUST-EMP-002",
                            created_at=SNAPSHOT, updated_at=SNAPSHOT))
        db.add(WorkflowTransition(task_id="TASK-TR-001", from_state=None, to_state="REQUESTED",
                                  actor="employee:EMP-002", reason="Transfer request submitted",
                                  occurred_at=SNAPSHOT))
    elif db.get(ShareTransferRequest, "TR-001").state == "REQUESTED" and (
        db.get(ShareTransferRequest, "TR-001").recipient_account_reference == "SEC-EMP-002"):
        db.get(ShareTransferRequest, "TR-001").recipient_account_reference = "CUST-EMP-002"
        task = db.get(WorkflowTask, "TASK-TR-001")
        if task:
            task.evidence_reference = "CUST-EMP-002"
    for account in db.scalars(select(StockAccount)):
        employee = db.get(Employee, account.employee_id)
        statement_id = f"STMT-STOCK-{account.employee_id}-2026"
        if not db.get(OperationalStatement, statement_id):
            db.add(OperationalStatement(id=statement_id, tenant_id=employee.tenant_id,
                                        employee_id=account.employee_id, service="stock",
                                        period="2026", as_of=SNAPSHOT.date(), version=1,
                                        source_reference=f"MEM-{account.employee_id}"))
    db.commit()

