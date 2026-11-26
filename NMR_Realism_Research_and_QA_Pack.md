# NMR Workplace Finance — Realism Research & Acceptance Pack

**Date:** 26 November 2026  
**Purpose:** Companion to `NMR_Workplace_Finance_V2_Functional_Blueprint.md` while Codex implements V2. This is a product/financial-domain review and QA specification, **not** permission to replace or overwrite ongoing code changes.  
**Context:** Fictional NMR provider; Toyota is a hypothetical corporate demo tenant; all employees, rules, prices, tax assumptions, instruments, account references, balances and activity are synthetic.

## 1. Product definition — what credible should mean

NMR is the *provider's operations system*. Its users manage plans, members, transaction records, exceptions, workflow queues, rules, reports and external-agent entitlements. The Toyota chatbot is an external consumer and is **not** the place to implement financial calculations or business authorization.

A high-fidelity simulation requires:

1. Financial **records** linked to the same employee / employer / plan / account identities.
2. Financial **events** with when they occurred, took effect and were recorded. Current balances derive from events or reconciled certified opening snapshots.
3. Configurable **plan-specific fictional rules**. Never silently represent a default incentive, threshold or treatment as a real Toyota or Nomura rule.
4. Domain **state machines**, where submitted ≠ approved ≠ posted ≠ settled ≠ completed.
5. **Errors and exceptions** with root causes, owners, supporting references and remediation—not decorative notifications.
6. **Evidence-based answers**, including references to ledger rows, plan rule versions and effective dates.
7. **Role separation**: provider operations, provider administrator, corporate plan admin, individual employee; a service ON toggle never grants administrator or execution rights.
8. **Client-facing contracts** and UI read the *same* backend records, not two independently hard-coded datasets.
9. A fully working denial when an NMR service is disabled, even if an agent cached its tool catalog.
10. Clear labeling of a **demo**; never imply live funds, real custody, regulatory approval, or a real Goldman Sachs/Toyota integration.

**Design target:** recognizable operational fidelity to someone familiar with Japanese workplace-finance products, without copying proprietary screens or asserting that Nomura runs this specific architecture.

## 2. Confirmed precedent versus fictional extension

| Domain | Confirmed public precedent | Fictional NMR extension | Avoid claiming |
|---|---|---|---|
| Shareholding | Nomura's employee shareholding association service: pooled periodic purchases, participant shares, employer-office processes, transfer to securities accounts | Configurable incentive, payroll reconciliation, purchase allocator, detailed event journal, admin exception work queue | Specific Toyota incentive rate or direct sale when withdrawing |
| Corporate pension | Nomura corporate DC: employer contributes, participant decides investments, valuation/simulation, participant instruction functionality | Synthetic fund NAV/positions, contribution batches, draft allocation and switch workflows | That provider itself holds/manages every pension asset or that plan limits are universal |
| Wellness | Nomura financial wellness research and education offerings | Employer benefit catalog, educational content approval, seminar/learning workflow | Individualized regulated financial advice or NISA account operation |
| Custody | Nomura Group trust / custody / depositary functions across legal entities | Limited employee-related synthetic asset servicing, dividend and transfer reconciliation | A single unified Nomura workplace custody portal |
| Equity compensation | Nomura corporate equity-compensation types; Equity Edge grants, payroll and reporting API precedents | Fictional grant, vesting, forfeiture, draft release, async plan reporting | Actual Nomura MCP access or agent trading permissions |

### Official reference links

- Nomura employee shareholding: https://www.nomura.co.jp/solution/business/corporate/mochikabu.html
- Nomura shareholding transfers: https://www.nomura.co.jp/support/procedure/shareholding/
- Nomura transfer-vs-sale FAQ: https://faq.nomura.co.jp/faq_detail.html?id=674
- Nomura share transfer status FAQ: https://faq.nomura.co.jp/faq_detail.html?id=137
- Nomura corporate DC plan responsibility: https://dc.nomura.co.jp/business/knowledge/outline.html
- Nomura participant DC web features: https://dc.nomura.co.jp/business/feature/web.html
- Nomura contribution allocation versus switching FAQ (iDeCo precedent, not every corporate-plan rule): https://dc.nomura.co.jp/ideco/faq/
- Nomura corporate equity compensation: https://www.nomura.co.jp/solution/business/corporate/stockcompensation.html
- Nomura public workplace digital services: https://www.nomura.co.jp/solution/digital/
- Nomura Group trust/custody boundary: https://www.nomuraholdings.com/en/services/banking.html
- Equity Edge Online API catalog: https://equityedgeonline.etrade.com/devportal/output/general/apidocumentation.html
- Equity Edge asynchronous vesting reporting: https://equityedgeonline.etrade.com/devportal/output/Reports/PersonnelVestingSummaryswagger.yaml.html
- Shareworks API security and tenancy precedent: https://downloads.shareworks.com/api/index.html

## 3. Define one connected, fully synthetic demo story

Use the *same employee and identifiers* across all five service domains. Values below are **candidate fixture assumptions for review**—replace or adapt them to existing tests rather than blindly inserting duplicates. Snapshot date: 2026-11-26, local business timezone: Asia/Tokyo, monetary unit: JPY.

**Tenant:** `toyota-demo` (hypothetical); **employee:** `TYO-001` / "Aiko Mori" (fictional); **employing legal entity:** `TYO-JP-01` (fictional); **plan rule version:** `RULE-TYO-2026-v1`; **employee status:** ACTIVE. A second wholly fictional tenant `harbor-demo` must be present for isolation tests. No real Toyota employee data or logos are necessary.

### 3.1 Stock ownership fixture — reconcilable transaction chain

Plan design assumptions for synthetic demonstration only: employee monthly election ¥20,000, illustrative employer incentive 5% of posted employee contribution, association permits fractional *beneficial interests* at its own recorded precision, and a synthetic transfer unit of 100 whole shares.

| Date / reference | Event | Employee cash | Employer incentive | Purchased beneficial units | State |
|---|---|---:|---:|---:|---|
| 2026-08-31 `OPEN-SH-001` | Reconciled opening beneficial interest | — | — | 138.50 existing units | CERTIFIED_OPENING |
| 2026-09-25 `PAY-SEP-001` | Payroll deduction posted | +20,000 | +1,000 | — | POSTED |
| 2026-09-30 `BUY-SEP-001` | Purchase allocated at ¥3,500/unit | -21,000 from cash | — | +6.00 | SETTLED_ALLOCATED |
| 2026-10-25 `PAY-OCT-001` | Payroll deduction posted | +20,000 | +1,000 | — | POSTED |
| 2026-10-31 `BUY-OCT-001` | Purchase allocated at ¥4,000/unit | -21,000 from cash | — | +5.25 | SETTLED_ALLOCATED |
| 2026-11-20 `PAY-NOV-001` | Missing/rejected payroll | 0 posted | 0 posted | 0 | REJECTED |
| 2026-11-24 `XFER-001` | 100 whole units transferred to linked eligible securities account | 0 | — | -100.00 | CONFIRMED_POSTED |

**Expected after transfer:** 49.75 association beneficial units; 100 whole shares in confirmed linked custody position; 149.75 combined ownership units for this *one security* (no double counting); ¥40,000 posted employee deductions, ¥2,000 posted synthetic incentives, ¥42,000 settled purchase cost, ¥0 uninvested contribution cash for this window. The certified opening holding is needed to explain earlier units; do not claim 149.75 units were all bought from only two months of contribution.

**Exception tickets:** `EX-SH-001` missing November payroll line; `EX-SH-002` duplicate September batch rejected before posting; `EX-SH-003` request for 150 whole-share transfer denied because available units after posted transfer are 49.75.

**Provider screens:** plan rules; member ledger; payroll import with rejected rows; purchase batch and allocation; withdrawal/transfer approval queue; reconciliations; statements; external access controls. Each row click opens a dated, source-referenced detail.

**Agent questions:**
- "Why didn't my November shares increase?" → rejected payroll event and no settled November purchase; never infer the cause from a static balance.
- "How much did I contribute this year?" → separate employee deductions, incentives, opening cash and purchase cost.
- "Have my transferred shares arrived?" → transfer `XFER-001` and linked custody credit, with time and status.
- "Can I sell my shareholding association units?" → explain transfer is separate from sale; no execution tool.

### 3.2 Corporate pension fixture — positions and contribution instructions

**Corporate DC plan assumption:** employer contributes monthly; employee top-up is allowed for this fictional plan via explicit plan rule (do not treat employee top-up as universal). Three synthetic fund positions at an as-of NAV: `DC-EQ-01` 50 units × ¥10,000 = ¥500,000; `DC-BD-01` 40 × ¥10,000 = ¥400,000; `DC-BAL-01` 35 × ¥10,000 = ¥350,000. **Total portfolio = ¥1,250,000** at the stated valuation date. All instruments/NAVs are fictional.

Current position weights calculated from holdings: 40% / 32% / 28%. The employee's future *contribution* allocation initially 70% equity / 30% bond / 0% balanced. A draft instruction changes future contributions to 50% / 30% / 20%. **Existing units 50/40/35 must remain unchanged** after posting the *future allocation* instruction. A separate switching workflow is required to change existing unit holdings, and that remains draft-only.

Exception scenarios: allocations sum to 105%; fund no longer eligible in this plan; contribution expected but not received; valuation date stale; transfer-out process after employment departure. Show institution boundaries: plan sponsor/employer, participant, recordkeeper and asset manager/custodian need not be the same entity.

### 3.3 Financial wellness fixture — approved content, not generic advice

Create a *tenant-specific benefits catalog* with dated rule versions and authoritative mock source references for the employer's stock plan and corporate DC plan. Keep at least one unpublished article and one expired article invisible to external APIs, plus published resources, learning progress, and a seminar registration with capacity.

Sample question: "What's the difference between my stock plan and DC pension?" A permitted tool returns two rule-document citations (`RULE-TYO-SH-v1`, `RULE-TYO-DC-v1`), effective dates, eligibility and differences—not an unsourced investment recommendation.

An illustrative savings calculator returns its formula identifier, explicit rate assumption, contribution frequency, horizon and reproducible total. Do not produce personalized tax advice, promise returns, or fabricate benefits missing from the tenant plan.

### 3.4 Custody fixture — one linked event, no double-counting

**Custody position:** source transfer `XFER-001`, `TYO-001`, same synthetic security, quantity +100 whole shares, state `SETTLED_CONFIRMED`. The participant's associated transfer-out is recorded exactly once in the shareholding ledger. Preserve one shared correlation ID across the two service records, but distinct business event IDs.

Separate sample action: `CA-002` announces a stock split for a *different synthetic security* with record/effective dates. Before effective posting, do **not** increase holdings; after a confirmed simulated split, post once and reconcile. Keep the split example distinct from the `XFER-001` securities to avoid accidental math conflicts.

Pending settlement is **not** available inventory. Dividend `ANNOUNCED` is not `PAID`; only posted cash credits affect cash. When custody MCP access is off but stock access is on, stock routes may report the *status of the association transfer* without leaking the restricted custody balance or full account details.

### 3.5 Equity compensation fixture — keep awards separate from shares

**RSU grant `RSU-001`:** synthetic 400-unit grant, tranches 100 vested / 300 scheduled as of 2026-11-26. The 100 vested units remain `VESTED_UNRELEASED` until a separate award-release event; they are **not** included in the participant's custody-share holdings. Exact schedule and rules are fictional.

**Option grant `OPT-001`:** 200 units granted; explicit strike price, vesting schedule, exercise window and expiration; `vested != exercised != delivered`. A draft option exercise performs validation but never orders/executes an actual trade.

**Terminated participant `TYO-006`:** a plan-specific rule forfeits an identified tranche; store effective termination time, rule version and a separate forfeiture event. Do not assume all terminated participants forfeit all awards.

**PSU `PSU-001`:** award has a hypothetical performance condition; earned quantity is `PENDING_CERTIFICATION` until an authorized mock certification event. Do not show unearned PSU shares as vested custody assets.

**Plan-level asynchronous report:** user requests a grants/vesting report; statuses `REQUESTED → RUNNING → READY` (or `FAILED`) with report snapshot date and immutable output reference. This is a *prototype pattern inspired by Equity Edge*, not a claim of identical wire contracts.

## 4. Five service-level review checklists

### Stock ownership
- [ ] Association beneficial interest is distinct from a directly held brokerage position.
- [ ] Member balances reconcile from source payroll and purchase batches or certified openings.
- [ ] Employer incentives are labeled as simulated, configurable plan rules.
- [ ] Failed/rejected payroll cannot increment cash, holdings or employer incentive postings.
- [ ] Transfer requires plan-specific eligible lot/quantity and recipient account reference.
- [ ] Transfer is not a sale; post in both services at most once.
- [ ] Admin screens expose approval queues, exceptions, and supporting references.

### Corporate pension
- [ ] Position valuation uses units × dated NAV, not unrelated dashboard amounts.
- [ ] Employer and optional employee contributions are distinguished.
- [ ] Contribution allocation instructions never change current unit holdings.
- [ ] Switching existing units is separately modeled and draft-only.
- [ ] Investment/fund catalogs, instruction statuses and stale NAV are shown.
- [ ] Projections label assumptions and do not promise returns.
- [ ] Plan-level access does not imply access to every employee's pension.

### Financial wellness
- [ ] Only published, current, tenant-authorized resources are externally returned.
- [ ] Every employer-specific benefit explanation links to a dated synthetic rule.
- [ ] Provider editors can approve/archive content; employee MCP cannot publish.
- [ ] Calculators disclose inputs, frequency, formula version and assumptions.
- [ ] No arbitrary recommendation of an investment instrument.
- [ ] Aggregate learning reports preserve individual privacy.

### Trust & custody
- [ ] Separate account and legal-entity model; don't claim custody sits in the stock website.
- [ ] Separate available/blocked/pending position quantities.
- [ ] Dividend entitlement / payment are separate.
- [ ] Corporate action posted only when effective and confirmed; idempotent.
- [ ] Transfers reference original association instruction and cross-service correlation.
- [ ] Reconciliation breaks carry real source references and resolution actions.

### Equity compensation
- [ ] RS, RSU, PSU and option have distinct behavior.
- [ ] Grant, award vesting, release, brokerage holding and sale are never conflated.
- [ ] Grant quantities reconcile across non-overlapping statuses.
- [ ] Termination treatment always points to configured plan rules.
- [ ] Option strike, expiration and exercise eligibility have explicit inputs.
- [ ] PSU certification precedes earned-unit finalization.
- [ ] Async reporting produces fixed, traceable snapshots rather than arbitrary chat output.

## 5. Permission demonstration — don't make one switch look like full governance

Minimum functional access policy:

`allow = valid_identity AND active_employee AND tenant_is_active AND tenant_master_mcp_enabled AND tenant_service_enabled AND principal_has_operation_scope AND requested_record_is_in_employee_scope`.

- The NMR admin interface can change **tenant master** and **individual service** access, persisting old/new state, actor, timestamp and reason.
- Separate *internal domain availability* from *external MCP access*: disabling pension MCP access does not stop NMR pension operations.
- Service OFF blocks every external route in that service, including report retrieval, calculations and drafts.
- A cached tool schema must never bypass server-side authorization on invocation.
- A combined wellness/benefits view must not expose fields from disabled stock, pension or equity domains; check all underlying permissions.
- Include tests for second tenant, suspended employee, wrong role, expired token, impersonation attempt, disabled domain and concurrent access revocation.
- No external tool may change admin permissions or execute real asset movements.
- A master switch is a useful POC control but **not** a replacement for enterprise identity, authorization, workflow approvals and regulatory controls.

## 6. Critical privacy boundary: employer versus employee

An employer-operated chatbot is **not** automatically entitled to everything in an employee's financial accounts. Separate the identity of the Toyota organization from the employee whose data is being requested. The agent should use a verified, scoped employee identity and must never retrieve arbitrary individual pension allocations, custody accounts, RSU grants or planning data merely because the corporate tenant has enabled the service.

- **Employee-scoped operations:** the authenticated participant may view their own benefit, balance, grant and custody records if allowed by the plan and service policy.
- **Employer administrator operations:** only documented employer-authorized aggregate or administrative records; no blanket access to individual investment preferences or unrelated personal accounts.
- **Provider operator operations:** NMR internal staff have role-scoped access needed to resolve operational cases; audit sensitive access.
- **Consent/notice:** the demo should visibly describe that responses contain synthetic personal financial records and that a real product needs contractual data-sharing authorization and consent/notice as applicable.
- **Agent context:** tool results may be visible in a chatbot session; an MCP ON/OFF switch does not remove already returned data. Minimize what is sent to model context and log no tokens or raw financial payloads in generic traces.

Test an employer-scoped credential attempting to query a different participant's holdings; it must fail even if both belong to the same tenant and all five service toggles are ON. This privacy boundary matters at least as much as the master toggle.

## 7. UI design: credibility from information architecture

Use restrained typography, neutral canvas, tight data tables, deliberate status colors and clear 4/8/12/16/24 spacing. Avoid gradients, large playful icons, invented marketing copy and unnecessary badges. Each service should have these **meaningful** affordances:

1. **Context header:** tenant → legal entity → plan → employee; data snapshot date, entity status, selected period.
2. **Service overview:** measures derived from records; pending items and anomalies with drill-through links.
3. **Operational queue:** actionable cases, current state, assigned operator, due date, source record and audit trail.
4. **Transaction or event journal:** original event, posted/recorded dates, status, amount/units, reconciliation reference.
5. **Detail drawer/page:** human-readable explanation of calculations, plan-rule version and linked records.
6. **Reports:** date ranges, inclusion/exclusion filters, generated as-of timestamps and downloadable synthetic CSV/PDF if implemented.
7. **Access panel:** master + five service switches per tenant, effective scope, change reason and audit events.

Make realistic empty/denied/error/stale states. Do not show invented live asset prices. Do not use real customer logos or imply official Nomura interfaces.

## 8. Four team demonstration scenarios (prepare concurrently with Codex)

| Demo | Employee prompt | Expected provider evidence | Why convincing |
|---|---|---|---|
| 1 — Missing shares | "Why were no shares bought for me in November?" | `PAY-NOV-001` rejected, zero November purchase, exception owner and resolution status | Shows workflow reasoning grounded in ledger |
| 2 — Pension change | "What if I change future contributions to 50/30/20?" | Current holdings 50/40/35 units unchanged, draft future allocation, correct 100% validation | Demonstrates important plan mechanics |
| 3 — Rights revoked | "Show my RSUs" before and after equity OFF | 200, then 403 `SERVICE_ACCESS_DISABLED`, while pension remains available; request IDs in audit | Genuine cross-enterprise entitlements |
| 4 — Transfer status | "Did my 100 shares move to my securities account?" | `XFER-001` association debit and custody credit share correlation; tenant permissions checked separately | Demonstrates linked systems without a sale or money movement |

**Good final demo:** show a business record in NMR → show the employee question → show permitted tool invocation → show dated evidence → disable the relevant service → show a real denied API call and audit entry. The Toyota chatbot does not need a custom financial rules engine.

## 9. Definition of realism complete (the actual exit gate)

A domain is ready only when:
- Financial metrics are derived from traceable events or a certified opening record.
- At least one full synthetic business workflow works across distinct lifecycle states.
- There is at least one meaningful failure, exception or reconciliation case.
- A reviewer can explain the calculation in the UI and its source references.
- An external API can retrieve the correct allowed information without administering the domain.
- A disabled service returns authorization denial at every externally reachable entry point.
- Negative cases, duplicate submissions and tenant isolation pass tests.
- No real data, external financial actions or unsourced claims about Nomura rules appear.

**What we should not build yet:** real custodian integration; payroll/broker production connectors; regulated tax rules; live quotes; a provider-side autonomous agent; complex A2A orchestration; real order execution; full Shareworks/EEO functionality; full Japanese pension regulatory logic.

## 10. Research uncertainties to ask a workplace-finance reviewer

1. Which product is the right representative story: Nomura employee shareholding web, corporate DC, or equity-compensation administration?
2. Which entity performs each step in payroll collection, share purchase, approval, share transfer and asset custody?
3. Which administrator roles actually approve association withdrawal/transfer and pension change requests?
4. Which plan rules vary by employer, and which are statutory? Who maintains them?
5. Which current APIs or export files are available, and who is permitted to invoke them?
6. Which employee records are contractually allowed to be disclosed to an external corporate AI?
7. Is there an existing API gateway, entitlement policy, delegated identity mechanism or MCP deployment pattern internally?
8. Which transactions would remain human-approved even if future agent-assisted workflows were introduced?

**Review rule:** If no business owner confirms these details, keep the rule explicitly fictional and label it as a configurable demo assumption.
