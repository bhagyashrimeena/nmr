"""Custody inventory and asset servicing, with separate transfer and cash events."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .security import ApiError, audit, require_client, require_provider
from .v2_models import (CustodyAccountV2, CustodyActionV2, CustodyDividendV2,
                        CustodySettlementConfirmation,
                        FinancialEvent, OperationalStatement, ShareTransferRequest)
from .v2_seed import SNAPSHOT

router = APIRouter(prefix="/api/v2", tags=["Trust and custody v2"])
AS_OF = date(2026, 11, 26)


def client_audit(db, request, claims, outcome="permitted", reason="OK"):
    request.state.principal_scopes = ",".join(claims.get("scopes") or [])
    audit(db, request, actor=claims["sub"], tenant_id=claims["tenant_id"],
          employee_id=claims["employee_id"], service="custody", outcome=outcome, reason=reason)


def account_for(db, tenant_id, employee_id):
    account = db.scalar(select(CustodyAccountV2).where(CustodyAccountV2.tenant_id == tenant_id,
                                                        CustodyAccountV2.employee_id == employee_id))
    if not account:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Custody account is not available.")
    return account


def event_rows(db, account):
    return list(db.scalars(select(FinancialEvent).where(
        FinancialEvent.tenant_id == account.tenant_id,
        FinancialEvent.employee_id == account.employee_id,
        FinancialEvent.service == "custody").order_by(FinancialEvent.effective_at, FinancialEvent.id)))


def position_json(db, account):
    events = event_rows(db, account)
    units = sum((x.quantity for x in events), Decimal("0"))
    cash = sum((x.amount_jpy for x in events), Decimal("0"))
    return {"account_id": account.id, "employee_id": account.employee_id,
            "instrument": account.instrument, "security_id": account.security_id,
            "ownership_basis": "INDIVIDUAL_SECURITIES_ACCOUNT",
            "opening_source_reference": f"CU-OPEN-{account.employee_id}",
            "as_of": AS_OF, "available_units": str(units), "cash_jpy": str(cash),
            "pending_transfer_units": str(sum((Decimal(x.units) for x in db.scalars(
                select(ShareTransferRequest).where(ShareTransferRequest.tenant_id == account.tenant_id,
                                                    ShareTransferRequest.employee_id == account.employee_id,
                                                    ShareTransferRequest.state != "COMPLETED"))), Decimal("0"))),
            "inventory_source": "CUSTODY_EVENTS_ONLY"}


def event_json(row):
    return {"id": row.id, "type": row.event_type, "source_reference": row.source_reference,
            "correlation_id": row.correlation_id, "effective_at": row.effective_at,
            "quantity": str(row.quantity), "amount_jpy": str(row.amount_jpy)}


def dividend_json(row):
    return {"id": row.id, "account_id": row.account_id, "record_date": row.record_date,
            "payment_date": row.payment_date, "entitlement_units": str(row.entitlement_units),
            "amount_jpy": str(row.amount_jpy), "state": row.state}


def action_json(row):
    return {"id": row.id, "account_id": row.account_id, "action_type": row.action_type,
            "record_date": row.record_date, "effective_date": row.effective_date,
            "numerator": row.numerator, "denominator": row.denominator,
            "eligible_units": str(row.eligible_units) if row.eligible_units is not None else None,
            "added_units": str(row.added_units) if row.added_units is not None else None,
            "state": row.state}


def transfers_for(db, account):
    return list(db.scalars(select(ShareTransferRequest).where(
        ShareTransferRequest.tenant_id == account.tenant_id,
        ShareTransferRequest.employee_id == account.employee_id)))


def transfer_json(db, row):
    confirmation = db.get(CustodySettlementConfirmation, row.id)
    return {"id": row.id, "employee_id": row.employee_id, "units": str(row.units),
            "state": row.state, "correlation_id": row.correlation_id,
            "settlement_state": confirmation.state if confirmation else "PENDING",
            "confirmation_reference": confirmation.confirmation_reference if confirmation else None}


@router.get("/client/me/custody/positions")
def client_positions(request: Request, db: Session = Depends(get_db),
                     claims: dict = Depends(require_client("custody"))):
    account = account_for(db, claims["tenant_id"], claims["employee_id"])
    result = position_json(db, account)
    client_audit(db, request, claims)
    return result


@router.get("/client/me/custody/history")
def client_history(request: Request, db: Session = Depends(get_db),
                   claims: dict = Depends(require_client("custody"))):
    account = account_for(db, claims["tenant_id"], claims["employee_id"])
    result = {"account_id": account.id, "events": [event_json(x) for x in event_rows(db, account)]}
    client_audit(db, request, claims)
    return result


@router.get("/client/me/custody/dividends")
def client_dividends(request: Request, db: Session = Depends(get_db),
                     claims: dict = Depends(require_client("custody"))):
    account = account_for(db, claims["tenant_id"], claims["employee_id"])
    rows = db.scalars(select(CustodyDividendV2).where(CustodyDividendV2.account_id == account.id)).all()
    client_audit(db, request, claims)
    return {"account_id": account.id, "dividends": [dividend_json(x) for x in rows]}


@router.get("/client/me/custody/actions")
def client_actions(request: Request, db: Session = Depends(get_db),
                   claims: dict = Depends(require_client("custody"))):
    account = account_for(db, claims["tenant_id"], claims["employee_id"])
    rows = db.scalars(select(CustodyActionV2).where(CustodyActionV2.account_id == account.id)).all()
    client_audit(db, request, claims)
    return {"account_id": account.id, "actions": [action_json(x) for x in rows]}


@router.get("/client/me/custody/transfers")
def client_transfers(request: Request, db: Session = Depends(get_db),
                     claims: dict = Depends(require_client("custody"))):
    account = account_for(db, claims["tenant_id"], claims["employee_id"])
    result = {"account_id": account.id, "transfers": [transfer_json(db, x) for x in transfers_for(db, account)]}
    client_audit(db, request, claims)
    return result


@router.get("/client/me/custody/settlements")
def client_settlements(request: Request, db: Session = Depends(get_db),
                       claims: dict = Depends(require_client("custody"))):
    account = account_for(db, claims["tenant_id"], claims["employee_id"])
    result = {"account_id": account.id, "settlements": [transfer_json(db, x) for x in transfers_for(db, account)]}
    client_audit(db, request, claims)
    return result


@router.get("/client/me/custody/statement")
def client_statement(request: Request, db: Session = Depends(get_db),
                     claims: dict = Depends(require_client("custody"))):
    account = account_for(db, claims["tenant_id"], claims["employee_id"])
    rows = db.scalars(select(OperationalStatement).where(
        OperationalStatement.tenant_id == account.tenant_id,
        OperationalStatement.employee_id == account.employee_id,
        OperationalStatement.service == "custody")).all()
    client_audit(db, request, claims)
    return {"account_id": account.id, "statements": [{"id": x.id, "period": x.period,
                                                       "as_of": x.as_of} for x in rows]}


class ReviewInput(BaseModel):
    state: str
    reason: str = Field(min_length=3, max_length=200)


@router.patch("/admin/tenants/{tenant_id}/custody/actions/{action_id}")
def review_action(tenant_id: str, action_id: str, body: ReviewInput, request: Request,
                  db: Session = Depends(get_db), claims: dict = Depends(require_provider("custody", write=True))):
    row = db.get(CustodyActionV2, action_id)
    if not row or row.tenant_id != tenant_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Corporate action is not available.")
    if (row.state, body.state) not in {("ANNOUNCED", "ENTITLEMENT_CAPTURED"),
                                       ("ENTITLEMENT_CAPTURED", "EFFECTIVE"),
                                       ("EFFECTIVE", "POSTED"), ("POSTED", "RECONCILED")}:
        raise ApiError(409, "STATE_CONFLICT", "Corporate action state change is not allowed.")
    account = db.get(CustodyAccountV2, row.account_id)
    if body.state == "ENTITLEMENT_CAPTURED":
        row.eligible_units = sum((event.quantity for event in event_rows(db, account)
                                  if event.effective_at.date() <= row.record_date), Decimal("0"))
    if body.state == "EFFECTIVE" and row.effective_date > AS_OF:
        raise ApiError(409, "NOT_EFFECTIVE", "Corporate action is not effective yet.")
    if body.state == "POSTED":
        row.added_units = row.eligible_units * (Decimal(row.numerator) / Decimal(row.denominator) - 1)
        if row.added_units < 0:
            raise ApiError(409, "INVALID_ACTION", "Action would create negative additional units.")
        event_id = "CU-ACTION-" + row.id
        if not db.get(FinancialEvent, event_id):
            db.add(FinancialEvent(id=event_id, tenant_id=tenant_id, employee_id=account.employee_id,
                                  service="custody", event_type="SPLIT_POSTED", source_reference=row.id,
                                  idempotency_key=event_id, correlation_id=row.id,
                                  occurred_at=SNAPSHOT, effective_at=SNAPSHOT, recorded_at=SNAPSHOT,
                                  amount_jpy=Decimal("0"), quantity=row.added_units,
                                  currency="JPY", actor=claims["sub"]))
    row.state = body.state
    request.state.operation = "review_corporate_action"
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=account.employee_id, service="custody", outcome="changed", reason=body.state)
    return action_json(row)


@router.patch("/admin/tenants/{tenant_id}/custody/dividends/{dividend_id}")
def review_dividend(tenant_id: str, dividend_id: str, body: ReviewInput, request: Request,
                    db: Session = Depends(get_db), claims: dict = Depends(require_provider("custody", write=True))):
    row = db.get(CustodyDividendV2, dividend_id)
    account = db.get(CustodyAccountV2, row.account_id) if row else None
    if not account or account.tenant_id != tenant_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Dividend is not available.")
    if (row.state, body.state) not in {("SCHEDULED", "PAID"), ("SCHEDULED", "FAILED")}:
        raise ApiError(409, "STATE_CONFLICT", "Dividend state change is not allowed.")
    if body.state == "PAID":
        if row.payment_date > AS_OF:
            raise ApiError(409, "NOT_PAYABLE", "Dividend payment date has not arrived.")
        event_id = "CU-CASH-" + row.id
        if not db.get(FinancialEvent, event_id):
            db.add(FinancialEvent(id=event_id, tenant_id=tenant_id, employee_id=account.employee_id,
                                  service="custody", event_type="DIVIDEND_PAID", source_reference=row.id,
                                  idempotency_key=event_id, correlation_id=row.id,
                                  occurred_at=SNAPSHOT, effective_at=SNAPSHOT, recorded_at=SNAPSHOT,
                                  amount_jpy=row.amount_jpy, quantity=Decimal("0"),
                                  currency="JPY", actor=claims["sub"]))
    row.state = body.state
    request.state.operation = "review_dividend"
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id,
          employee_id=account.employee_id, service="custody", outcome="changed", reason=body.state)
    return dividend_json(row)


@router.get("/admin/tenants/{tenant_id}/custody/operations")
def admin_custody_operations(tenant_id: str, request: Request, db: Session = Depends(get_db),
                             claims: dict = Depends(require_provider("custody"))):
    accounts = list(db.scalars(select(CustodyAccountV2).where(CustodyAccountV2.tenant_id == tenant_id)))
    account_ids = [x.id for x in accounts]
    actions = list(db.scalars(select(CustodyActionV2).where(CustodyActionV2.tenant_id == tenant_id)))
    dividends = list(db.scalars(select(CustodyDividendV2).where(CustodyDividendV2.account_id.in_(account_ids))))
    request.state.operation = "view_custody_operations"
    audit(db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=None,
          service="custody", outcome="permitted", reason="OK")
    return {"tenant_id": tenant_id, "as_of": AS_OF,
            "accounts": [position_json(db, x) for x in accounts],
            "actions": [action_json(x) for x in actions],
            "dividends": [dividend_json(x) for x in dividends],
            "transfers": [transfer_json(db, x) for account in accounts for x in transfers_for(db, account)]}
