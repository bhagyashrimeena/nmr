"""Provider-only V2 participant record. Financial data derives from the operational journal.

Never expose this provider-admin route via the employee-facing MCP adapter.
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Employee
from .security import ApiError, audit, require_admin
from .v2_models import (
    CustodyAccountV2, CustodyActionV2, CustodyDividendV2, EquityAward,
    FinancialEvent, PensionFundPosition, ShareMembership,
)
from .stock_v2 import stock_summary
from .pension_v2 import pension_account
from .custody_v2 import position_json, dividend_json, action_json
from .equity_v2 import award_json
from .v2_seed import SNAPSHOT

router = APIRouter(tags=["Provider · Authoritative V2 Records"])
SERVICES = {"stock", "pension", "custody", "equity"}


def _journal(db: Session, tenant_id: str, employee_id: str, service: str):
    events = db.scalars(
        select(FinancialEvent).where(
            FinancialEvent.tenant_id == tenant_id,
            FinancialEvent.employee_id == employee_id,
            FinancialEvent.service == service,
        ).order_by(FinancialEvent.effective_at, FinancialEvent.id)
    ).all()
    return [
        {
            "id": row.id,
            "type": row.event_type,
            "effective_at": row.effective_at,
            "source_reference": row.source_reference,
            "correlation_id": row.correlation_id,
            "amount_jpy": str(row.amount_jpy),
            "quantity": str(row.quantity),
        }
        for row in events
    ]


@router.get("/api/v2/admin/tenants/{tenant_id}/employees/{employee_id}/source-record/{service}")
def provider_employee_record(
    tenant_id: str,
    employee_id: str,
    service: str,
    request: Request,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_admin()),
):
    if service not in SERVICES:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "This V2 financial domain is not available.")
    employee = db.get(Employee, employee_id)
    if not employee or employee.tenant_id != tenant_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Participant record is not available for this client.")

    result = {
        "tenant_id": tenant_id,
        "employee_id": employee_id,
        "employee_name": employee.display_name,
        "service": service,
        "as_of": SNAPSHOT.date(),
        "source_version": "V2_LEDGER",
        "currency": "JPY",
        "available": False,
        "summary": None,
        "journal": _journal(db, tenant_id, employee_id, service),
        "details": [],
    }

    if service == "stock":
        member = db.scalar(select(ShareMembership).where(ShareMembership.employee_id == employee_id))
        if member:
            result["available"] = True
            result["summary"] = stock_summary(db, tenant_id, employee_id)

    elif service == "pension":
        fund_position = db.scalar(select(PensionFundPosition).where(PensionFundPosition.employee_id == employee_id))
        if fund_position:
            result["available"] = True
            result["summary"] = pension_account(db, tenant_id, employee_id)
            result["details"] = result["summary"]["positions"]

    elif service == "custody":
        account = db.scalar(select(CustodyAccountV2).where(
            CustodyAccountV2.tenant_id == tenant_id, CustodyAccountV2.employee_id == employee_id
        ))
        if account:
            result["available"] = True
            result["summary"] = position_json(db, account)
            result["details"] = {
                "dividends": [
                    dividend_json(row) for row in db.scalars(
                        select(CustodyDividendV2).where(CustodyDividendV2.account_id == account.id)
                    )
                ],
                "actions": [
                    action_json(row) for row in db.scalars(
                        select(CustodyActionV2).where(CustodyActionV2.account_id == account.id)
                    )
                ],
            }

    elif service == "equity":
        awards = db.scalars(select(EquityAward).where(EquityAward.employee_id == employee_id)
                            .order_by(EquityAward.grant_date, EquityAward.id)).all()
        result["available"] = bool(awards)
        result["details"] = [award_json(db, award) for award in awards]
        result["summary"] = {
            "grant_count": len(awards),
            "granted_units": sum(award.granted_units for award in awards),
            "reconciled": all(item["reconciled"] for item in result["details"]),
        }

    request.state.operation = "read_v2_participant_source"
    request.state.principal_scopes = ",".join(claims.get("scopes") or [])
    audit(
        db, request, actor=claims["sub"], tenant_id=tenant_id, employee_id=employee_id,
        service=service, outcome="permitted", reason="V2_PARTICIPANT_SOURCE",
    )
    return result
