from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class Purchase(BaseModel):
    purchase_date: date
    shares: int
    price_jpy: int
    amount_jpy: int
    status: str
    reference: str


class Contribution(BaseModel):
    month: date
    amount_jpy: int
    employer_incentive_jpy: int


class StockStatement(BaseModel):
    period: str
    employee_contributions_jpy: int
    employer_incentives_jpy: int
    shares_purchased: int
    purchase_cost_jpy: int


class StockActivity(BaseModel):
    date: date
    type: str
    amount_jpy: int
    shares: int


class StockResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    currency: str
    plan_id: str
    plan_name: str
    enrollment_date: date | None
    participation_status: str
    employer_incentive_percent: int
    shares_held: int
    monthly_contribution_jpy: int
    total_contributions_jpy: int
    year_to_date_contributions_jpy: int
    employer_incentives_jpy: int
    uninvested_cash_jpy: int
    average_purchase_cost_jpy: str
    illustrative_share_price_jpy: str
    illustrative_portfolio_value_jpy: int
    illustrative_unrealized_change_jpy: int
    current_quarter_purchased_shares: int
    dividends_received_jpy: int
    contributions: list[Contribution]
    recent_purchases: list[Purchase]
    purchases: list[Purchase]
    activity: list[StockActivity]
    statements: list[StockStatement]
    note: str


class Allocation(BaseModel):
    asset_class: str
    percentage: int
    illustrative_value_jpy: int


class PensionContributionItem(BaseModel):
    date: date
    employee_amount_jpy: int
    employer_amount_jpy: int


class Projection(BaseModel):
    starting_balance_jpy: int
    monthly_contribution_jpy: int
    years: int
    annual_return_pct: str
    total_contributed_jpy: int
    illustrative_future_value_jpy: int
    illustrative_growth_jpy: int
    disclaimer: str


class ProjectionResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    currency: str
    purpose: str
    projection: Projection


class PensionValuationItem(BaseModel):
    date: date
    balance_jpy: int
    illustrative_nav: str


class PensionStatement(BaseModel):
    period: str
    employee_contributions_jpy: int
    employer_contributions_jpy: int


class PensionResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    currency: str
    account_type: str
    plan_name: str
    enrollment_status: str
    balance_jpy: int
    opening_balance_jpy: int
    employee_contributions_jpy: int
    employer_contributions_jpy: int
    employer_contributions_ytd_jpy: int
    investment_change_jpy: int
    equity_allocation_percent: int
    illustrative_nav_change_percent: str
    allocations: list[Allocation]
    recent_contributions: list[PensionContributionItem]
    contribution_history: list[PensionContributionItem]
    valuation_history: list[PensionValuationItem]
    projection: Projection
    statements: list[PensionStatement]
    note: str


class WellnessItem(BaseModel):
    id: str
    title: str
    topic: str
    description: str
    content: str
    progress: str


class WellnessProgressSummary(BaseModel):
    completed: int
    in_progress: int


class WellnessProgressPatch(BaseModel):
    status: Literal["not_started", "in_progress", "completed"]


class WellnessResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    resources: list[WellnessItem]
    topics: list[str]
    preferred_topic: str | None
    recommended_resources: list[WellnessItem]
    progress: WellnessProgressSummary
    note: str


class CustodyPositionItem(BaseModel):
    instrument: str
    quantity: int
    security_id: str
    asset_class: str
    illustrative_price_jpy: str
    illustrative_value_jpy: int


class DividendItem(BaseModel):
    payment_date: date
    record_date: date | None
    instrument: str
    amount_jpy: int
    status: str


class CorporateActionItem(BaseModel):
    id: str
    instrument: str
    title: str
    record_date: date | None
    effective_date: date
    status: str


class SettlementItem(BaseModel):
    id: str
    instrument: str
    trade_date: date
    settlement_date: date
    quantity: int
    status: str


class CustodyStatement(BaseModel):
    period: str
    dividends_credited_jpy: int
    settled_events: int


class CustodyValuationItem(BaseModel):
    date: date
    illustrative_value_jpy: int


class CustodyResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    currency: str
    account_id: str
    account_status: str
    opened_on: date
    illustrative_portfolio_value_jpy: int
    dividends_received_ytd_jpy: int
    pending_corporate_actions: int
    positions: list[CustodyPositionItem]
    dividends: list[DividendItem]
    corporate_actions: list[CorporateActionItem]
    settlements: list[SettlementItem]
    valuation_history: list[CustodyValuationItem]
    statements: list[CustodyStatement]
    note: str


class VestingItem(BaseModel):
    vest_date: date
    units: int
    status: str


class GrantItem(BaseModel):
    id: str
    award_type: str
    grant_date: date
    plan_name: str
    vesting_condition: str
    granted_units: int
    vested_units: int
    unvested_units: int
    forfeited_units: int
    released_units: int
    exercised_units: int
    exercise_eligible_units: int
    exercise_price_jpy: str | None
    expiry_date: date | None
    illustrative_share_price_jpy: str
    illustrative_award_value_jpy: int
    vesting_events: list[VestingItem]


class EquitySummary(BaseModel):
    grant_count: int
    vested_units: int
    unvested_units: int
    exercise_eligible_options: int


class EquityStatement(BaseModel):
    grant_id: str
    grant_date: date
    award_type: str
    granted_units: int
    vested_units: int


class EquityResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    grants: list[GrantItem]
    next_vesting: VestingItem | None
    summary: EquitySummary
    statements: list[EquityStatement]
    note: str


class McpPatch(BaseModel):
    enabled: bool
    reason: str = Field(min_length=3, max_length=200)


class McpResponse(BaseModel):
    tenant_id: str
    enabled: bool
    changed_by: str
    changed_at: datetime
    reason: str
    services: list["ServiceAccess"]
    effective_service_count: int


class ServiceAccess(BaseModel):
    service: str
    title: str
    description: str
    route: str
    enabled: bool
    effective_enabled: bool
    changed_by: str
    changed_at: datetime
    reason: str


class AccessChangeItem(BaseModel):
    id: int
    request_id: str
    actor: str
    tenant_id: str
    service: str
    previous_enabled: bool
    new_enabled: bool
    reason: str
    created_at: datetime


class AdminLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
