from datetime import date, datetime

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


class Contribution(BaseModel):
    month: date
    amount_jpy: int


class StockResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    currency: str
    plan_id: str
    shares_held: int
    monthly_contribution_jpy: int
    total_contributions_jpy: int
    contributions: list[Contribution]
    recent_purchases: list[Purchase]


class Allocation(BaseModel):
    asset_class: str
    percentage: int


class PensionContributionItem(BaseModel):
    date: date
    employee_amount_jpy: int
    employer_amount_jpy: int


class PensionResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    currency: str
    account_type: str
    balance_jpy: int
    employee_contributions_jpy: int
    employer_contributions_jpy: int
    investment_change_jpy: int
    allocations: list[Allocation]
    recent_contributions: list[PensionContributionItem]
    note: str


class WellnessItem(BaseModel):
    id: str
    title: str
    topic: str
    description: str
    content: str


class WellnessResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    resources: list[WellnessItem]
    note: str


class CustodyPositionItem(BaseModel):
    instrument: str
    quantity: int


class DividendItem(BaseModel):
    payment_date: date
    instrument: str
    amount_jpy: int
    status: str


class CorporateActionItem(BaseModel):
    id: str
    instrument: str
    title: str
    effective_date: date


class CustodyResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    currency: str
    positions: list[CustodyPositionItem]
    dividends: list[DividendItem]
    corporate_actions: list[CorporateActionItem]


class VestingItem(BaseModel):
    vest_date: date
    units: int
    status: str


class GrantItem(BaseModel):
    id: str
    award_type: str
    grant_date: date
    granted_units: int
    vested_units: int
    unvested_units: int
    vesting_events: list[VestingItem]


class EquityResponse(BaseModel):
    tenant_id: str
    employee_id: str
    as_of: date
    grants: list[GrantItem]
    next_vesting: VestingItem | None


class McpPatch(BaseModel):
    enabled: bool
    reason: str = Field(min_length=3, max_length=200)


class McpResponse(BaseModel):
    tenant_id: str
    enabled: bool
    changed_by: str
    changed_at: datetime
    reason: str


class AdminLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
