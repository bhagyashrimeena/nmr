"""Stable identifiers shared by tenant policy, API routes, and the provider UI."""

SERVICES = {
    "stock": {"title": "Employee Stock Ownership", "description": "Payroll contributions, share purchases, holdings and statements", "route": "/api/v1/client/me/stock-ownership"},
    "pension": {"title": "Corporate Pension", "description": "Contributions, allocations, valuations and projections", "route": "/api/v1/client/me/pension"},
    "wellness": {"title": "Financial Wellness", "description": "Educational resources, progress and savings calculators", "route": "/api/v1/client/wellness/resources"},
    "custody": {"title": "Trust & Custody", "description": "Positions, dividends, corporate actions and settlements", "route": "/api/v1/client/me/custody"},
    "equity": {"title": "Equity Compensation", "description": "RSUs, options, vesting and award history", "route": "/api/v1/client/me/equity-compensation"},
}
