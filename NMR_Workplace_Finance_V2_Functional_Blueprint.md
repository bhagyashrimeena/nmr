# NMR Workplace Finance POC — V2 Functional Blueprint

**Status:** Proposed engineering specification for review  
**Date:** 26 November 2026  
**Audience:** NMR provider-side developer, Toyota MCP adapter developer, AI engineering team  
**System:** Fictional NMR workplace-finance platform; hypothetical Toyota tenant; synthetic employee and financial data only  
**Do not represent NMR as a real financial institution or this architecture as a Nomura production implementation.**

## 0. Decision and product intent

NMR must behave like a small, realistic **financial-operations platform**, not five unrelated dashboards. Each service is a bounded business domain with several workflows, related records, financial controls, human-oriented operational screens, exceptions, reconciliations and read-only (or explicitly draft-only) tenant-scoped APIs. The Toyota AI chatbot and MCP server are owned by another developer. NMR provides the authoritative REST services and independently enforces access.

**Existing baseline:** `bhagyashrimeena/nmr`, branch `feat/workplace-finance-detailed-provider`, directory `provider-standalone/`. As reviewed 26 November: five rich JSON summary endpoints, a pension and savings calculator, master and per-service toggles, audit records and test data. This is an excellent connectivity baseline but not an operations lifecycle. Preserve the working API contracts while extending the domain model.

**Evidence versus design:** Nomura's public digital workplace services include its Shareholding Web Service, Corporate DC Pension Net, and Workplace Accumulation NISA Web. The project team's five domains instead consist of Stock Ownership, Pension, Financial Wellness, Trust & Custody, and Equity Compensation. Stock Ownership and Pension have direct public product precedents. Equity Compensation has a corporate product precedent but is not demonstrated to be a fully unified employee workplace portal. Financial Wellness is related to education and workplace offerings. Trust & Custody is a broader financial group capability. All five together constitute a fictional unified NMR platform.

### Definition of 'detailed'

A detailed module must have: (a) real business entities; (b) an operational summary; (c) detail pages and searchable lists; (d) at least one stateful workflow; (e) transparent calculations; (f) exception-handling cases; (g) report/statement views; (h) traceable event history; (i) external read APIs; (j) tests of financial invariants and authorization.

**Non-goals:** Live investment, live trading, actual payroll deductions, real pension switching, real asset movement, regulated advice, impersonation of Nomura systems, unapproved production deployment, third-party employee data, direct chatbot access to administrative controls.

## 1. Shared platform contracts — before service expansion

### 1.1 Organization and identity

- `tenant`: fictional corporation, e.g. `toyota-demo`; second fictional tenant needed for isolation checks.
- `legal_entity`: employing entity / plan sponsor; linked to tenant.
- `employee`: employee identifier, tenant, legal entity, status, employment dates and benefit eligibility.
- `membership`: which employee belongs to which plan, including start/end dates and enrollment status.
- `account`: product-specific account reference; not every employee has all five services.
- `principal`: NMR platform administrator, NMR operations user, hypothetical Toyota plan administrator, Toyota employee / signed chatbot representative.
- Distinguish *corporate group*, *employer legal entity*, *plan*, *employee*, *account*, and *external client* identifiers. A client-supplied employee ID must not override authenticated identity.

### 1.2 Entitlements

Use an enforceable policy function: `authorize(principal, tenant, service_key, operation_key, resource_scope)`.

The effective permission for any external request is: 

`authenticated && active_tenant && tenant_master_mcp_enabled && tenant_service_enabled && principal_scope_allows_operation && employee_or_plan_in_scope`.

Persist `tenant_service_permission(tenant_id, service_key, enabled, updated_by, updated_at)`. Add optional future `tenant_operation_permission(tenant_id, service_key, operation_key, mode)`; modes `DENY`, `READ`, `DRAFT` (never real execution in POC). **Always enforce server-side at call time, including when an MCP client caches tool descriptions**. NMR internal admin screens remain available when external service access is off. The global switch does not overwrite individual switch states. Log both permitted and denied operations.

### 1.3 Shared business infrastructure

- Immutable financial activity/event journal, with `occurred_at`, `effective_at`, `recorded_at`, source reference, actor and idempotency key.
- Decimal money and quantity values; explicit JPY currency and fixed rounding/contribution conventions.
- Source identifiers for payroll batches, purchases, securities, investment funds, corporate actions, grants and requests.
- Deterministic fixture clock and snapshot date (2026-11-26) rather than runtime random prices or current system date.
- Reconciliation and exception cases, with `OPEN`, `INVESTIGATING`, `RESOLVED`, `WAIVED` and a resolution note.
- Request/approval tasks, with designated reviewer roles, evidence, state history and no automatic final financial execution.
- Statements and reports generated from stored domain events, with `as_of`, source references and report version.
- Optional asynchronous synthetic reports: `REQUESTED -> RUNNING -> READY/FAILED`, to mirror Equity Edge's documented report-submit/status/results pattern; not essential for every service.

### 1.4 Shared portal UI patterns

Each service uses the same structure, but domain-specific content:

1. **Overview** — operational KPIs, time period and snapshot age.
2. **Accounts/participants** — searchable table, filters and real row detail.
3. **Workflow queue** — pending approvals, exceptions and simulated operational actions.
4. **History/ledger** — dated records and traceable references.
5. **Statements/reports** — aggregate and employee-specific reporting.
6. **Configuration** — plan rules and status (read-only for general staff; editable only in dedicated sandbox admin flows).
7. **Service external access** — read-only status indicator linking to NMR Admin's actual tenant controls.

No fabricated dashboard metric without a source record; no production-style 'live' market claims for fixed fixture data. Make empty/error/loading states real.

## 2. Service 1 — Employee Stock Ownership (highest priority)

### 2.1 Authentic domain premise

Inspired by Nomura's employee shareholding association / 持株WEB. Employees contribute via payroll, a shareholding association buys employer shares under its own rules, individual participation interests are tracked, employer incentive plans may apply, dividends may be reinvested. Nomura publicly describes employer-office processing and approved transfer of eligible association holdings to a securities account; **a withdrawal/transfer request is NOT an equity sale or cash-out**.

Public references: [Nomura employee shareholding](https://www.nomura.co.jp/solution/business/corporate/mochikabu.html), [Nomura shareholding support](https://www.nomura.co.jp/support/procedure/shareholding/), [Shareholding Web](https://www.e-plan.nomura.co.jp/login/start.html).

### 2.2 NMR operator personas

- Plan operations: configure a synthetic plan, membership rules, payroll processing periods, incentive rules and purchase schedule.
- Payroll reconciliation operator: import/correct synthetic batches and resolve duplicates/missing contributions.
- Share allocation operator: review a purchase batch, match cash to shares and post participant beneficial interests.
- Corporate plan administrator: review members' contribution and transfer requests.
- Employee: view own balances, contributions, purchases, dividends, statements and request status.

### 2.3 Business objects

`shareholding_plan`, `membership`, `contribution_election`, `payroll_batch`, `payroll_line`, `employer_incentive_line`, `purchase_batch`, `purchase_allocation`, `share_balance_event`, `dividend_event`, `share_transfer_request`, `securities_account_reference`, `reconciliation_break`, `statement`.

Never equate a payroll contribution with settled shares. Distinguish cash reserve from beneficial share interests; permit fractional beneficial units if the mock plan rules explicitly allow them, and apply an explicit whole-share transfer minimum rule if configured.

### 2.4 Detailed internal screens

| Screen | User questions and functions | Key columns |
|---|---|---|
| Plan overview | Which plan, purchase dates, incentives and participation rules? | Plan, issuer, enrollment status, contribution rules, incentive percentage, next purchase |
| Member directory | Who is participating and with what election? | Employee, status, joined, monthly election, cash, share units |
| Payroll batches | Which payments were received, rejected or unmatched? | Batch, period, expected, received, matched, failed count, state |
| Purchase cycles | Which contributions became shares? | Batch, trade date, unit price, allocated units, residual cash, status |
| Holdings ledger | Why did this participant's balance change? | Timestamp, event type, shares +/-, cash +/-, source |
| Transfer requests | Where is an employee's transfer request? | Request, units, recipient-account reference, company approval, provider status |
| Reports & breaks | What failed or doesn't reconcile? | Period, break type, expected, actual, owner, resolution |

### 2.5 Workflows and invariants

**A. Enrollment and election:** `SUBMITTED -> ELIGIBILITY_CHECKED -> APPROVED -> EFFECTIVE` or `REJECTED`; a changed contribution election applies no earlier than the plan's synthetic effective payroll period. Validate min/max amount and account status.

**B. Payroll collection:** `RECEIVED -> VALIDATED -> POSTED` or `PARTIALLY_REJECTED`; one payroll line per `(employee_id, period, source_batch_reference)` and a deterministic duplicate policy. Posted cash increases the participant cash ledger, not shares.

**C. Purchase batch:** `CREATED -> PRICED -> SETTLED -> ALLOCATED`; employee contributions + employer incentives + opening uninvested cash = purchase outflows + closing uninvested cash. Shareholding position increases **only** after `SETTLED` and allocation. Settlement may fail; do not allocate failed purchases.

**D. Dividend:** `DECLARED -> ENTITLEMENT_FIXED -> PAID/REINVESTED` or `FAILED`; entitlements based on holdings as of mock record date, not arbitrary present holdings.

**E. Transfer (draft/simulation only):** `REQUESTED -> ELIGIBILITY_CHECKED -> CORPORATE_APPROVED -> PROVIDER_FORWARDED -> COMPLETED` or `REJECTED/CANCELLED`. Check account reference, whole-share minimum if applicable and available transferable balance. On simulated completion transfer units out of the association; a securities-account credit in the synthetic custody service is a linked **separate** event. No sale is placed.

**Invariants:** `settled_purchase_units + opening_units + reinvestment_units - transferred_units = current_units`; `posted_employee_cash + posted_incentive_cash + opening_cash + dividend_reinvestment_cash - settled_purchase_cost - released_cash = closing_cash`. All ledger events idempotent with immutable refs.

### 2.6 Client-facing API contract (PROPOSED, not existing Nomura APIs)

- `GET /api/v2/client/me/shareholding/summary`
- `GET /api/v2/client/me/shareholding/contributions?from=&to=`
- `GET /api/v2/client/me/shareholding/purchases?from=&to=`
- `GET /api/v2/client/me/shareholding/dividends`
- `GET /api/v2/client/me/shareholding/ledger`
- `GET /api/v2/client/me/shareholding/transfers/{request_id}`
- Optional `POST /api/v2/client/me/shareholding/transfer-drafts` -> sandbox draft only, with explicit operation scope and idempotency.

**Sample employee queries:** “Why were no shares added last month?”, “How much did I contribute this year?”, “What is my available whole-share withdrawal amount?”, “What happened to transfer request TR-001?”

### 2.7 Acceptance tests

- Payroll duplicate rejected without double posting.
- Missing payroll does not increment shares.
- Contribution + incentive - settled purchase reconciles to residual cash.
- Partial purchase allocation does not allocate more units than batch acquired.
- Transfer in `REQUESTED` does not alter ledger; `COMPLETED` alters it exactly once.
- Stock service OFF denies every stock endpoint, not pension.
- Employee cannot retrieve another member's transfer request.

## 3. Service 2 — Corporate Pension (direct Nomura precedent)

### 3.1 Product premise and reference

Inspired by Nomura's defined-contribution pension web service. Participant views include balances, fund-level gains/losses, target-return simulations, and investment-product changes. **Changing allocations for future contributions does not switch existing holdings**. Nomura explicitly distinguishes contribution-allocation change from switching current assets. [Nomura DC web](https://dc.nomura.co.jp/business/feature/web.html); [Nomura FAQ](https://dc.nomura.co.jp/ideco/faq/).

### 3.2 Business objects

`dc_plan`, `plan_product`, `participant_pension_account`, `contribution_batch`, `participant_contribution`, `fund`, `nav_snapshot`, `unit_position`, `future_contribution_allocation`, `allocation_instruction`, `switching_instruction`, `plan_statement`, `fund_restriction`, `pension_exception`.

### 3.3 Screens

- Plan enrollment & employer contribution schedule.
- Pension participant accounts with current valuations and vesting/eligibility constraints where modeled.
- Contribution batches (expected vs received vs posted).
- Investment product catalog with fund categories and fees, all illustrative.
- Holdings breakdown with units × dated NAV and cumulative cash-flow reconciliation.
- Future contribution allocations distinct from current holdings.
- Instruction work queue: validated draft allocation change or synthetic switching request.
- Retirement projections with assumptions, fee disclosure, comparison of 0%, 2%, 4% scenarios and no assurance of returns.
- Reconciliation reports and rejected-contribution investigations.

### 3.4 Core flows

**Contribution:** `EXPECTED -> RECEIVED -> POSTED -> INVESTED` or `REJECTED`; the account value changes according to dated cash and NAV events, not unexplained random totals.

**Future allocation:** `DRAFT -> VALIDATED -> ACCEPTED -> EFFECTIVE_NEXT_CONTRIBUTION`; verify fund eligibility, 100% allocation, funding source and available plan rules; leave current unit positions unchanged.

**Current asset switch (optional draft-only):** `DRAFT -> VALIDATED -> SIMULATION_PREVIEW -> AWAITING_APPROVAL`; show prospective fund units and potential fees; never execute actual investments.

**Projection:** deterministic calculation from current balance, monthly future contribution, time horizon and explicit hypothetical return assumption. Do not claim statistical probability of reaching a target unless a proper stochastic model is implemented.

### 3.5 External read/draft API suggestions

`/api/v2/client/me/pension/account`, `/contributions`, `/positions`, `/funds`, `/allocation`, `/projections`, `/instructions/{id}`; optional `POST /allocation-drafts`.

**Acceptance:** 100% future allocation, no change in existing asset units when future allocation changes; stale NAV marked; rejected contributions excluded from invested balance; pension service OFF blocks all pension routes.

## 4. Service 3 — Financial Wellness (related offering; not the same as a plan ledger)

### 4.1 Product premise

Employer-specific educational content, benefit explanations and scenario calculators. Do not represent it as regulated personalized investment advice. Treat approved content with publication dates and sources; prevent the LLM from making up plan rules. This is a fictional service architecture informed by Nomura's workplace financial education and financial wellness initiatives.

### 4.2 Business objects

`benefits_catalog_entry`, `education_program`, `learning_path`, `content_item`, `content_revision`, `review_approval`, `seminar`, `seminar_registration`, `progress_record`, `calculator_scenario`, `education_feedback`.

### 4.3 Screens

- Employer program setup, participant cohorts and available benefits.
- Content library filtered by category, level, language, publication status and review expiry.
- Editorial approval queue (draft, in review, approved, published, archived).
- Learning pathways & participation metrics.
- Webinar and seminar scheduling with mock registrations and attendance.
- Financial calculators: monthly savings; retirement gap; benefit comparison (explicit assumptions).
- Reporting with aggregated learning metrics; no inappropriate display of private personal assessment results.

### 4.4 Flows and guardrails

Content review: `DRAFT -> IN_REVIEW -> APPROVED -> PUBLISHED -> ARCHIVED`; external clients only see published content. An expired item is excluded or clearly flagged.

Benefit explanation: cite the exact tenant plan rule document and `effective_date`; if absent, return `BENEFIT_RULE_NOT_AVAILABLE` rather than a generic invented policy. The LLM may explain; the service provides truth.

Calculators: output inputs, rate assumptions, period, formula ID and disclosures. Never infer the user's risk appetite or recommend a financial instrument.

### 4.5 External capabilities

`search_approved_education`, `get_tenant_benefit_explanation`, `get_learning_path`, `get_education_progress`, `list_seminars`, `calculate_savings`.

**Acceptance:** unpublished/expired content not exposed; calculations reproducible; tenant-specific benefit comparisons require valid rules; wellness OFF blocks educational retrieval and calculator API (the calculator must not bypass policy).

## 5. Service 4 — Trust & Custody (fictional unified-workplace extension)

### 5.1 Important boundary

Custody is a separate institution-level function in many banking groups and may involve different legal entities and systems. The NMR demo combines a *limited personal securities asset-servicing view* into the fictional workplace platform. **Do not claim Nomura's documented shareholding website is also its full custody platform.**

### 5.2 Business objects

`custody_account`, `security_master`, `position_lot`, `position_event`, `transfer_instruction`, `settlement_event`, `dividend_entitlement`, `dividend_payment`, `corporate_action`, `corporate_action_election`, `reconciliation_break`, `statement`.

### 5.3 Screens

- Account registry/status and beneficiary ownership.
- Position details: available, blocked, pending, instrument identifiers and dated valuation.
- Settlement monitor: transfer instructions and confirmation references.
- Dividend processing: ex-date/record date/payment date, announced vs paid.
- Corporate action event register (stock splits and distributions), with effective date and affected positions.
- Reconciliation monitor: expected vs recorded assets and exceptions.
- Statements and date-range transactions.

### 5.4 Workflows and invariants

**Corporate action:** `ANNOUNCED -> ENTITLEMENT_CAPTURED -> EFFECTIVE -> POSTED -> RECONCILED` or `CANCELLED`; a 2-for-1 split of 100 eligible shares creates 100 additional shares only when effective and posted; no artificial doubling of economic market value. Reprocessing must be idempotent.

**Shareholding transfer:** consume the `COMPLETED` association transfer event with the same correlation ID; post matching custody credit exactly once. Pending transfer is visible but not available inventory. Stock-ownership and custody views must not double-count transferred units.

**Dividends:** entitlement quantity fixed at record date; `ANNOUNCED`, `SCHEDULED`, `PAID`, `FAILED` are distinct; only `PAID` affects cash balance.

**Settlement:** can be `PENDING`, `MATCHED`, `SETTLED`, `FAILED`, `CANCELLED`; do not report success before confirmation.

### 5.5 External capabilities

`get_custody_positions`, `get_position_history`, `get_dividend_entitlements`, `get_corporate_action_details`, `get_transfer_status`, `get_settlement_status`, `get_custody_statement`.

**Acceptance:** fractional/unavailable shares not transferred in contradiction to plan rules; split applied once; dividend cash changes only on paid event; custody service OFF blocks even if stock service ON.

## 6. Service 5 — Equity Compensation (direct corporate product precedent; Equity Edge is a useful benchmark)

### 6.1 Domain foundation

Nomura's corporate stock-compensation product page describes restricted stock, RSUs, PSUs, stock options, stock-delivery trusts and shareholding-linked incentives. E*TRADE Equity Edge Online's public catalog includes participant imports, grant setup/update, vesting and transaction reporting, release/exercise records, plans, entitlements and audit. **Existing APIs do not imply external MCP agents can execute those operations.** [Nomura product](https://www.nomura.co.jp/solution/business/corporate/stockcompensation.html); [Equity Edge API catalog](https://equityedgeonline.etrade.com/devportal/output/general/apidocumentation.html).

### 6.2 Business objects

`equity_plan`, `plan_share_reserve`, `participant_eligibility`, `award_grant`, `grant_term`, `grant_approval`, `award_acceptance`, `vesting_tranche`, `performance_condition`, `employment_event`, `forfeiture_event`, `release_instruction`, `tax_withholding_estimate`, `exercise_draft`, `award_ledger`, `report_job`.

### 6.3 Screens

- Plan rules, award types, share reserve and remaining authorizations.
- Eligible participants and employment status history.
- Grants: detail, approvals, dates, quantities and acceptance.
- Vesting engine: scheduled, vested, forfeited and accelerated mock scenarios.
- Option eligibility: strike, exercise window, vested/exercisable and expired units.
- Release queue: draft withholding estimates, confirmation and settlement status.
- Plan-level reconciliation and exposure reports.
- Exceptions: termination treatment, invalid schedule, exceeded reserve, duplicated grant, withheld release.
- Audit history by grant, employee and plan.

### 6.4 Financial mechanics and states

**Grant:** `PROPOSED -> APPROVED -> ISSUED -> ACTIVE` or `REJECTED/CANCELLED`; if plan requires acceptance, add an acceptance event. A proposed grant must not be counted as legally issued.

**Vesting:** scheduled tranches evaluated against time, employment and explicitly configured plan conditions. `granted_units = scheduled_unvested + vested_unreleased + released + forfeited + other_explicit_reconciled_states` (non-overlapping categories). Vested does **not** always equal delivered, exercisable, or available for sale.

**Options:** separately calculate `vested`, `exercised`, `expired`, `forfeited`, `currently_exercisable`; validate exercise period and strike; do not automatically use equity price as executable market price.

**PSU:** performance multiplier is not final until hypothetical performance certification; do not assign earned units before certification.

**Release:** `PREPARED -> VERIFIED -> APPROVED -> SIMULATED_RELEASED`; any custody delivery requires a distinct linked confirmation event. Tax results are explicitly synthetic, not country-specific compliance advice.

**Plan report:** optional async job `SUBMITTED -> RUNNING -> READY/FAILED`, including plan-as-of, award type, count, reserve, vested and outstanding quantities. This parallels a documented EEO report workflow without claiming compatibility.

### 6.5 External capabilities

`get_my_grants`, `get_grant_details`, `get_vesting_schedule`, `get_option_eligibility`, `get_award_release_history`, `get_equity_statement`; optional `prepare_option_exercise_draft` with no execution rights.

**Acceptance:** grant reserve never negative, 100% reconcile, termination only applies configured plan rules, vesting/release distinct, draft exercise never results in real sale or share transfer, equity service OFF gates all routes.

## 7. Multi-service scenarios and consistency

1. **Shareholding transfer to custody:** Transfer request goes from stock ownership to a confirmed custody credit. Same correlation ID, distinct service permissions, no duplicate share counting. If custody access is OFF, its status must not leak through a 'global overview' endpoint.
2. **RSU release to custody:** Issued/vested/released shares are not custody assets until delivery is confirmed. A pending release is visible in equity only if authorized.
3. **Pension + wellness:** Benefit explanation uses approved employer rules and an educational projection; never blends a synthetic projection with actual current valuation.
4. **Employee unified view:** It is a *composition* of service results, not a privileged bypass. Retrieve only services allowed under current effective tenant and principal scope; show 'unavailable/disabled' without the value of blocked domains.
5. **Off/on demonstration:** Master ON, Stock ON, Pension ON, Equity OFF; stock and pension continue to work while equity is denied. Master OFF denies all external operations without disabling NMR internal admin pages or erasing service settings.

## 8. API versioning, tools and privilege separation

Keep v1 summary endpoints for teammate compatibility while introducing detailed v2 resources. Avoid exposing internal administrative actions in the MCP tool catalog.

Suggested approved tool levels:

| Level | Meaning | Example | POC policy |
|---|---|---|---|
| READ | Retrieve records or statements | `get_my_grants` | Allowed when service and principal enabled |
| CALCULATE | Deterministic simulation | `calculate_retirement_scenario` | Allowed when relevant service enabled |
| DRAFT | Prepare a request with no settlement or financial impact | `prepare_allocation_change` | Explicit separate grant and confirm/approval workflow |
| EXECUTE | Trade, transfer money/assets, release real shares | None | Always unavailable |

**Important:** The externally used MCP server may expose multiple tools for one service. Admin switching one service off must block every tool in that service at NMR API authorization. Where a tool composes data from multiple services, it must verify each source independently or omit unavailable fields. Never rely only on tool-discovery filtering.

### Error contract

401 `UNAUTHENTICATED`; 403 `MCP_ACCESS_DISABLED`, `SERVICE_ACCESS_DISABLED`, `INSUFFICIENT_PERMISSIONS`, `RESOURCE_NOT_ACCESSIBLE`; 404 `RESOURCE_NOT_FOUND`; 409 `STATE_CONFLICT`, `DUPLICATE_REQUEST`, `RECONCILIATION_FAILED`; 422 `INVALID_PLAN_RULE`, `INVALID_ALLOCATION`, `INVALID_AMOUNT`, `INVALID_DATE_RANGE`; 503 `DATA_SNAPSHOT_UNAVAILABLE`. Include opaque `request_id` and safe end-user message; log restricted technical details internally.

## 9. Synthetic data design

- 2 fictional employers: Toyota demo tenant and one second isolated tenant; at least 10–15 synthetic employees for Toyota and 4–6 for second tenant.
- Distinct profiles: fully enrolled; stock-only; pension-only; just joined; left employment; inactive; has equity grant; no custody account; pending transfer; missed payroll; disputed settlement.
- At least 12 monthly payroll and pension cycles, 2 share purchases with different prices, dividends and a rejected batch. Every financial value derives from these records.
- At least 3 corporate pension funds with dated mock NAVs and allocations.
- At least 1 stock split and 1 shareholding-to-custody transfer, with correlating event IDs and dates.
- At least 2 RSU grants, 1 option grant, 1 PSU conditional grant, forfeiture and future vesting tranche.
- At least 6 published wellness articles, 2 learning paths, a scheduled seminar and 1 archived resource excluded from external queries.
- Always include snapshot date and label all prices, currencies, tax rates, contribution limits and plan rules as **synthetic assumptions**, never actual Toyota or Nomura employee records.

## 10. Engineering rollout and tests

**Stage A — Foundation:** Preserve v1, add normalized, separate domain tables and migration scripts (avoid treating one JSON document as the whole durable financial ledger); shared audit, tenant data, event journal, timestamps, access guards and error contracts.

**Stage B — Stock Ownership:** Implement plan/member details, payroll batch and purchase settlement, linked ledger, exceptions and transfer draft; expose 4–6 v2 read routes; 15–20 meaningful test scenarios.

**Stage C — Pension:** Contribution/valuation logic, investment positions, future allocation instruction draft (distinct from holdings switch), projections and exceptions.

**Stage D — Equity:** Plan/grants/vest tranches, employment event edge cases, releases as simulated distinct state and async report demo.

**Stage E — Custody:** Corporate action and dividend ledger, settlement statuses, stock association transfer coordination; test double-counting risk.

**Stage F — Wellness:** Approved content system, employer benefit rules, learning progress, calculators and governance.

**Stage G — Admin & demo:** Detail pages, searchable lists, transaction timeline, state and exception queue, reports; 5 toggles and master, API error panel, clear status labels and full audit. Teammate MCP integration remains separately owned.

### Cross-cutting mandatory test matrix

- For each of five services: authorized request 200, disable service -> 403, re-enable -> 200; other service remains accessible.
- Master OFF denies every client route; re-enable restores pre-existing service settings.
- Caller cannot impersonate a different employee or tenant; admin and employee token roles separate.
- Draft/approval endpoints reject external principals lacking explicit operation permission.
- Duplicate payroll, purchase, transfer, vest and corporate action events are idempotent or safely rejected.
- Reconciliations are deterministic and survive process restart.
- Cross-service statement values reconcile and cannot disclose disabled domains.
- Audit includes correlation ID, actor, principal scope, service, operation, outcome, timestamp and reason without token/secrets.
- Snapshot date and stale data clearly shown in responses.

## 11. Demo narrative for the AI engineering review

**Story 1 — Financial integrity:** A Toyota employee asks why their shareholding didn't increase last month. The NMR payroll batch records a rejected contribution. No shares were allocated; the app shows error, remediation and ledger. The chatbot retrieves the explanation through 2–3 read tools, not a fabricated guess.

**Story 2 — Fine-grained external entitlements:** NMR admin disables Equity Compensation for Toyota. Pension and Stock remain readable. Every equity request returns 403 and a logged denied event. Re-enabling restores it; master OFF denies all.

**Story 3 — Cross-service but no execution:** A share transfer draft is approved in the fictional association workflow and eventually confirmed with an idempotent custody credit. The client can check both status and holdings when authorized. No actual shares, cash or pension assets are moved.

**Success criterion:** A bank operations reviewer can trace any answer to records, rules and dated events; a security reviewer can independently prove denial; a teammate can call documented NMR APIs without inventing financial logic in the MCP adapter.

## 12. Primary reference register and evidence limitations

- Nomura employee shareholding and administration: https://www.nomura.co.jp/solution/business/corporate/mochikabu.html — describes group purchasing, membership, contributions, dividends, company admin access and withdrawals; does not disclose internal APIs.
- Nomura shareholding Web capabilities: https://www.e-plan.nomura.co.jp/login/start.html — publicly listed member functionality; does not establish MCP support.
- Nomura shareholding transfer and custody sequence: https://www.nomura.co.jp/support/procedure/shareholding/ — documents employer-office transfer request, brokerage-account transfer, and subsequent sale; does not authorize agent execution.
- Nomura DC web services: https://dc.nomura.co.jp/business/feature/web.html — account valuations, simulations and product-change views; no public MCP implementation.
- Nomura DC allocation versus switching FAQ: https://dc.nomura.co.jp/ideco/faq/ — explains future-contribution allocation versus switching existing holdings; iDeCo-specific FAQ, not proof every corporate plan allows identical rules.
- Nomura equity compensation: https://www.nomura.co.jp/solution/business/corporate/stockcompensation.html — describes RS/RSU/PSU/options; does not prove unified NMR service or specific API rights.
- Nomura public digital workplace offerings: https://www.nomura.co.jp/solution/digital/ — confirms Shareholding WEB, DC Net and workplace NISA WEB; broader group custody and the five-tab product are fictional integration concepts.
- E*TRADE Equity Edge Online official API catalog: https://equityedgeonline.etrade.com/devportal/output/general/apidocumentation.html — confirms diverse admin REST APIs and reporting categories; no evidence that the same tools are externally MCP-exposed.
- EEO vesting report: https://equityedgeonline.etrade.com/devportal/output/Reports/PersonnelVestingSummaryswagger.yaml.html — submit/status/results pattern.
- EEO plan summary: https://equityedgeonline.etrade.com/devportal/output/Reports/PlanSummaryswagger.yaml.html — aggregate activity/reserve reporting, async report contract.

**Research gaps needing business stakeholders:** exact Japanese workplace plan rules, transfer approval allocation, legal-entity custody responsibility, employer incentives, tax treatment, consent, plan-specific limits, participant privacy, whether API access exists internally, and whether external chatbot access is permissible. Keep all POC rules as explicitly fictional until confirmed.
