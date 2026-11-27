# Provider operations verification

**Record date:** 26 November 2026. **Application:** NMR Workplace Finance provider. The standalone HTML reference was reviewed for navigation and record-detail patterns; its browser-local controls were not used as the application's financial source.

## Population and source controls

The persisted register contains three corporate clients, 15 client-service agreements, and 256 participants. The original four employee records are retained. The added 252 participants have deterministic employment cohorts, department and hire dates, pension histories, and eligibility-dependent stock, custody, equity, and wellness records. Repeating the population seed does not duplicate employees or agreements. Financial amounts are tied to payroll, purchase, NAV, award, position, or journal rows rather than UI constants.

The service report endpoint accepts an `as_of` date no later than 26 November 2026. It sums stored journal entries and reports case references. A paginated source endpoint lets an operator inspect every event behind the aggregate. Equity awards and published wellness content are counted from their domain tables. Participant reports expose dated event IDs, source references, correlations, and existing statement references.

## Business scenarios

| Service | Persisted workflow checked | Failure or control checked |
|---|---|---|
| Stock Ownership | A rejected November contribution is inspected at the line level. An evidenced correction creates a new posted batch, the dated rule link, employee cash and incentive entries, and a resolved case. The rejected batch remains; shares do not increase until a purchase allocation. A confirmed transfer posts equal stock-out and custody-in quantities. | Repeated correction, mismatched elections, duplicate posted periods, ineligible custody account, missing settlement confirmation, and disabled stock service are rejected. |
| Corporate Pension | Fund units multiplied by dated NAVs reconcile to account value. A future-allocation instruction leaves existing holdings alone. A separate switch draft leaves holdings and future allocation unchanged. | Rejected contribution is excluded from invested value; employee scope and pension switch denial are tested. |
| Financial Wellness | Published current content, benefit-source references, and explicit calculator assumptions are returned. | Draft or expired content is withheld. Stock and pension benefit explanations cannot bypass their underlying service permissions. |
| Trust & Custody | A completed association transfer requires settlement evidence and linked journal entries. A corporate action captures record-date entitlement and posts once. | Announced dividends do not create paid cash; transfer and corporate-action state conflicts are rejected. |
| Equity Compensation | Issued awards reconcile grant, vested, scheduled, released, exercised, and forfeited quantities. Grant, vesting, release and custody states are distinct. | Proposed awards are not exposed to employee read routes; option drafts do not execute an exercise; service gating applies. |

## Authorization

- Platform administrator: all provider administration routes.
- Tenant-scoped service operator: only granted V2 service read/write routes, such as `ops:stock:read` and `ops:stock:write` for Toyota stock operations. The same token fails on pension, another tenant, and V1 administrator routes.
- Corporate plan administrator: aggregate tenant counts and service agreement references only; no employee IDs or personal financial routes.
- Employee: signed tenant and employee identity, service eligibility, active status, scope, and current master/service switches are all required for protected client routes.
- Disabled service: new calls fail while unrelated enabled services continue. The master switch supersedes individual settings and preserves their saved values.

## Evidence

Backend suite: **59 passed**. Frontend production build, HTTP access-control smoke, and automated browser smoke passed. Browser verification covered all five service screens, a rejected payroll batch detail, the three-client agreement register, participant search, work queue, operational reports, access management, and audit records.

Screenshots: [participants](screenshots/participant-directory.png), [client agreements](screenshots/client-agreements.png), [work queue](screenshots/work-queue.png), [reports](screenshots/operational-reports.png), [stock operations](screenshots/stock-operations.png), [access management](screenshots/access-management.png).

## Remaining limits

The proposed exact 149.75-unit opening transfer scenario is still unseeded; existing opening stock and custody inventories have separate sources. The stock operator UI now has payroll and purchase controls, while bank reconciliation and association dividends need more depth. Pension switch execution, comprehensive custody lots and failed-settlement recovery, PSU certification, full education revision and seminar attendance histories, and database-enforced append-only policy remain future work. The Toyota chatbot and MCP adapter are separate and have not been tested end to end with this provider. The local authentication and static values are for evaluation, with no real accounts or financial execution.
