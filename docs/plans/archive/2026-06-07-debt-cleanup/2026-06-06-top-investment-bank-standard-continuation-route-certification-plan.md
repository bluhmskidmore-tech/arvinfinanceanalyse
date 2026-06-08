# Top Investment Bank Standard Continuation Route Certification Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from strong institutional frontend surfaces to route-scoped, evidence-backed top-investment-bank certification without false approval claims.

**Architecture:** Treat top-investment-bank standard as a governed certification system, not a visual polish label. Run two lanes in parallel where possible: close human-gated evidence for routes already in `evidence-pending`, and build direct Gate I lanes for routes still in `gate-i-gap`. Keep every route's formal-use, golden-sample, governance, manual-audit, and owner-approval boundary explicit until real evidence closes it.

**Tech Stack:** Python readiness scripts, pytest, Markdown evidence packets, MOSS page contracts, metric dictionary, golden sample catalog, MCP evidence surfaces, PowerShell readiness wrappers, frontend browser/a11y/build checks, existing route-specific frontend/backend tests.

---

## Current Verdict

The system has not reached full top-investment-bank business certification.

Evidence:

- `docs/audits/2026-06-06-top-investment-bank-certification-board.md:32` says no route is currently `business-contract-certified`.
- `docs/audits/2026-06-06-route-scope-classification.md:31` reports `business-contract-certified = 0`.
- `/product-category-pnl`, `/pnl-attribution`, and `/ledger-pnl` are in `evidence-pending`, not certified.
- `/bond-analysis` and `/stock-analysis` are in `gate-i-gap`.
- Visible unseeded routes still exist and cannot be treated as closed system coverage.

Allowed claim:

> MOSS has strong institutional frontend surfaces and controlled business-certification lanes. Full top-investment-bank business certification is still route-scoped and open.

Forbidden claim:

> MOSS, or any route, is fully top-investment-bank business-certified before direct golden approval, manual audit closure, and captured business-owner approval all exist.

## RALPLAN-DR Summary

### Principles

1. Certification is evidence closure, not screenshot quality.
2. Every route needs direct evidence; no page borrows another page's contract, sample, or owner approval.
3. Candidate, DTO-only, observational, and formal surfaces must stay visibly separated.
4. Generated packets prepare human review; they never become approval.
5. UI polish is valuable only when it improves decision confidence and preserves metric traceability.

### Decision Drivers

1. The hard blocker is business evidence: golden approval, manual audit closure, owner approval, and route-specific Gate I lanes.
2. `/bond-analysis` is the best next Codex-actionable lane because it has a clear Gate I gap and an existing direct lane document.
3. `/product-category-pnl` remains the best first true certification candidate, but its remaining blockers require human review/signature.

### Viable Options

| Option | Pros | Cons | Decision |
| --- | --- | --- | --- |
| A. More frontend polish first | Fast visual lift | Does not reduce certification blockers | Reject as primary lane |
| B. Close `/product-category-pnl` owner packet | Closest to first certified route | Needs human owner/golden/manual audit evidence | Keep as owner lane |
| C. Build `/bond-analysis` direct Gate I lane | Codex can reduce a structural certification gap now | Still remains non-certified until approval | Choose for next execution |
| D. Build `/stock-analysis` first | Important surface | Policy-sensitive; must avoid trading-instruction claims | Do after bond lane |

## Target Standard

A route reaches top-investment-bank business standard only when all gates below pass:

| Gate | Required proof |
| --- | --- |
| First-screen business conclusion | The page answers one primary business question before decorative or secondary content. |
| Traceable metric chain | API response -> adapter/transformer -> state/selector -> component -> chart/table is documented and tested. |
| Unit/date/null semantics | Units, precision, rounding, date basis, stale/fallback state, null vs zero, and currency scale are explicit. |
| Direct page contract | Route, page ID, primary API, decision surface, and formal/candidate boundary are route-specific. |
| Metric dictionary | Metric IDs and rules are direct to this page or explicitly marked candidate/observational. |
| Golden sample | A route-scoped sample exists, is non-placeholder, and has approval metadata. |
| Catalog/date evidence | Source tables and date freshness are sampled or explicitly routed for direct review. |
| Governance evidence | Direct page/API governance validation is ready or written with authorization. |
| Manual audit | Human review closes metric, lineage, UI, API, sample, and live-smoke evidence. |
| Business-owner approval | Strict checker reports captured owner approval with non-placeholder owner, approver, date, and acceptance fields. |
| Browser quality | Desktop/tablet/mobile have no blocking console errors, no horizontal overflow, no broken empty/error/stale states, and pass targeted a11y/build checks. |

## Next Execution Order

### Task 1: Freeze The Certification Boundary

**Files:**

- Inspect: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`
- Inspect: `docs/audits/2026-06-06-route-scope-classification.md`
- Inspect: `scripts/codex_page_readiness.py`
- Test: `tests/test_codex_page_readiness_gate.py`

**Step 1: Rerun route-scope readiness**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
```

Expected:

- `business_contract_certified_count=0`
- `evidence_pending_count=12`
- `gate_i_gap_count=2`
- `next_gate_i_gap_routes` includes `bond-analysis` and `stock-analysis`

**Step 2: Run the route-scope tests**

Run:

```powershell
python -m pytest tests\test_codex_page_readiness_gate.py -q -k "route_scope or bond_analysis or stock_analysis"
```

Expected: pass.

**Acceptance Criteria:**

- The board still prevents false certification claims.
- The next work queue remains route-scoped and evidence-first.

### Task 2: Keep `/product-category-pnl` As The First Human Certification Candidate

**Files:**

- Inspect: `docs/pnl/product-category-pnl-first-certification-packet.md`
- Inspect: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-remaining-blockers.md`
- Script: `scripts/check_product_category_pnl_business_owner_approval.py`
- Script: `scripts/product_category_pnl_first_certification_packet.py`
- Script: `scripts/product_category_pnl_owner_decision_packet.py`
- Test: `tests/test_product_category_pnl_business_owner_approval_status.py`
- Test: `tests/test_product_category_pnl_first_certification_packet.py`
- Test: `tests/test_product_category_pnl_owner_decision_packet.py`

**Step 1: Regenerate packets if evidence changed**

Run:

```powershell
python scripts\product_category_pnl_first_certification_packet.py
python scripts\product_category_pnl_owner_decision_packet.py
```

Expected:

- Packet remains `business_contract_certified=false`.
- Blocker count remains machine-consistent with `docs/pnl/product-category-remaining-blockers.md`.

**Step 2: Run the owner checker**

Run:

```powershell
python scripts\check_product_category_pnl_business_owner_approval.py
```

Expected:

- `captured=false`
- action items remain visible

**Step 3: Run strict checker as an expected blocker**

Run:

```powershell
python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected: fail until a real owner supplies non-placeholder approval.

**Step 4: Verify packet/checker consistency**

Run:

```powershell
python -m pytest tests\test_product_category_pnl_business_owner_approval_status.py tests\test_product_category_pnl_first_certification_packet.py tests\test_product_category_pnl_owner_decision_packet.py -q
```

Expected: pass.

**Acceptance Criteria:**

- `/product-category-pnl` remains the first true certification candidate.
- The route is not promoted unless strict approval is captured.
- No generated document is treated as human approval.

### Task 3: Build The Direct `/bond-analysis` Gate I Lane

**Files:**

- Inspect: `docs/audits/2026-06-06-bond-analysis-gate-i-lane.md`
- Modify: `docs/page_contracts.md`
- Modify: `docs/metric_dictionary.md`
- Modify: `docs/golden_sample_catalog.md`
- Create: `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/`
- Create: `docs/pnl/bond-analysis-business-owner-approval-template.md`
- Create: `docs/pnl/bond-analysis-owner-evidence-packet.md`
- Create: `docs/pnl/bond-analysis-sign-off-packet.md`
- Create: `scripts/check_bond_analysis_business_owner_approval.py`
- Create: `scripts/bond_analysis_owner_evidence_packet.py`
- Modify: `scripts/codex_page_readiness.py`
- Modify: `scripts/mcp/moss_project_mcp.py`
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_golden_samples_capture_ready.py`
- Test: `tests/test_project_mcp_servers.py`
- Create: `tests/test_bond_analysis_business_owner_approval_status.py`
- Create: `tests/test_bond_analysis_owner_evidence_packet.py`

**Step 1: Write failing tests for the intended boundary**

Add tests that require:

- `/bond-analysis` does not borrow `PAGE-BOND-001`.
- `/bond-analysis` does not borrow `GS-BOND-HEADLINE-A`.
- A new sample ID, `GS-BOND-ANALYSIS-ACTION-ATTR-A`, is route-scoped to `GET /api/bond-analytics/action-attribution`.
- The route remains `formal_use_allowed=false`.
- The route is not `business-contract-certified`.

Run:

```powershell
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_golden_samples_capture_ready.py -q -k "bond_analysis or bond"
```

Expected: fail before implementation.

**Step 2: Add a direct page contract candidate**

Update `docs/page_contracts.md` with a route-specific `/bond-analysis` section:

- page ID: `PAGE-BOND-ANALYSIS-001` only if the repo's contract naming pattern allows promotion from `GAP-BOND-ANALYSIS-PAGE`; otherwise keep the GAP ID and mark it `candidate_contract`.
- route: `/bond-analysis`
- primary API: `GET /api/bond-analytics/action-attribution`
- supporting APIs: dates, DV01, KRD, return decomposition, benchmark excess, credit-spread migration, portfolio headlines, top holdings, position changes, yield-curve term structure
- boundary: fixed-income decision cockpit candidate only; `formal_use_allowed=false`

**Step 3: Add candidate metric rows**

Update `docs/metric_dictionary.md` with direct candidate rows for the first-screen decision values only:

- action-attribution PnL
- duration action/change
- period start/end DV01
- warning count/detail
- report date and period type
- result_meta basis/formal-use state

Each row must include:

- `status=candidate`
- unit and precision review status
- sign/null/date rule
- source endpoint
- `bound_page_id`
- `bound_sample_id=GS-BOND-ANALYSIS-ACTION-ATTR-A`
- `pending_confirmation=true`

Do not add formal metric truth unless human-approved metric dictionary evidence exists.

**Step 4: Create the capture-ready sample directory**

Create `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/` with the existing golden-sample directory pattern:

- `metadata.json`
- `response.json`
- `assertions.md`
- `approval.md`

Required sample status:

- `artifact_status=captured-awaiting-approval`
- `sample_boundary=page_dto_only` or `fixed_income_action_attribution_dto_only`
- `formal_use_allowed=false`
- owner/approver/date fields remain pending unless real human evidence exists

**Step 5: Add the owner evidence lane**

Add `scripts/check_bond_analysis_business_owner_approval.py` and packet generator:

- approval defaults to pending
- strict `--require-captured` fails
- action items include direct contract review, metric dictionary review, sample review, catalog/date review, governance review, live smoke review, and candidate-boundary acceptance

**Step 6: Wire readiness and MCP evidence**

Update readiness/MCP surfaces so `/bond-analysis` reports:

- direct route contract candidate exists
- direct sample exists and is pending approval
- formal use remains false
- governance/manual/owner remain open
- classification may move from `gate-i-gap` to `evidence-pending` only if the direct Gate I lane is actually complete

**Step 7: Verify the focused lane**

Run:

```powershell
python scripts\codex_page_readiness.py --page-slug bond-analysis
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_bond_analysis_business_owner_approval_status.py tests\test_bond_analysis_owner_evidence_packet.py -q
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_golden_samples_capture_ready.py tests\test_project_mcp_servers.py -q -k "bond_analysis or bond"
```

Expected:

- all focused tests pass
- `/bond-analysis` is not certified
- `formal_use_allowed=false`
- `--require-captured` remains an expected strict failure

**Acceptance Criteria:**

- `/bond-analysis` has a direct Gate I lane that does not borrow `/bond-dashboard`.
- The route has a capture-ready sample boundary and owner packet.
- The system can explain exactly why `/bond-analysis` is still not certified.

### Task 4: Close Candidate-Boundary Evidence For `/ledger-pnl` And `/pnl-attribution`

**Files:**

- Inspect: `docs/pnl/ledger-pnl-owner-evidence-packet.md`
- Inspect: `docs/pnl/ledger-pnl-sign-off-packet.md`
- Inspect: `docs/pnl/pnl-attribution-owner-evidence-packet.md`
- Inspect: `docs/pnl/pnl-attribution-sign-off-packet.md`
- Script: `scripts/check_ledger_pnl_business_owner_approval.py`
- Script: `scripts/check_pnl_attribution_business_owner_approval.py`
- Script: `scripts/ledger_pnl_owner_evidence_packet.py`
- Script: `scripts/pnl_attribution_owner_evidence_packet.py`
- Test: `tests/test_ledger_pnl_business_owner_approval_status.py`
- Test: `tests/test_ledger_pnl_owner_evidence_packet.py`
- Test: `tests/test_pnl_attribution_business_owner_approval_status.py`
- Test: `tests/test_pnl_attribution_owner_evidence_packet.py`

**Step 1: Refresh ledger and attribution packets**

Run:

```powershell
python scripts\ledger_pnl_owner_evidence_packet.py
python scripts\pnl_attribution_owner_evidence_packet.py
```

Expected:

- both remain `business_contract_certified=false`
- both expose candidate/DTO-only boundary
- no governance write is performed

**Step 2: Run strict checkers as expected blockers**

Run:

```powershell
python scripts\check_ledger_pnl_business_owner_approval.py --require-captured
python scripts\check_pnl_attribution_business_owner_approval.py --require-captured
```

Expected: fail until real owner approval exists.

**Step 3: Verify packet tests**

Run:

```powershell
python -m pytest tests\test_ledger_pnl_business_owner_approval_status.py tests\test_ledger_pnl_owner_evidence_packet.py tests\test_pnl_attribution_business_owner_approval_status.py tests\test_pnl_attribution_owner_evidence_packet.py -q
```

Expected: pass.

**Acceptance Criteria:**

- The pages remain evidence-pending with honest candidate boundaries.
- Generated packets are ready for human review.
- No formal-use or approval flag is promoted.

### Task 5: Build The `/stock-analysis` Observational Gate I Lane After Bond

**Files:**

- Inspect: `docs/plans/2026-05-30-stock-analysis-backend-supply-dashboard-ralplan.md`
- Modify: `docs/page_contracts.md`
- Modify: `docs/metric_dictionary.md`
- Modify: `docs/golden_sample_catalog.md`
- Modify: `scripts/codex_page_readiness.py`
- Modify: `scripts/mcp/moss_project_mcp.py`
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_project_mcp_servers.py`

**Step 1: Write the observational boundary tests**

Require:

- route remains observational
- `formal_use_allowed=false`
- no trading instructions
- no standalone `MTR-STOCK-*` formal metric truth unless explicitly approved

Run:

```powershell
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_project_mcp_servers.py -q -k "stock_analysis or stock"
```

Expected: fail before implementation if direct boundary is missing.

**Step 2: Add direct observational contract**

Document `/stock-analysis` as decision-support diagnostics, not formal advice:

- route: `/stock-analysis`
- approval status: observational/candidate
- sample boundary: DTO-only pending approval if a sample is captured
- explicit forbidden claim: no trading instruction or recommendation certification

**Step 3: Verify**

Run:

```powershell
python scripts\codex_page_readiness.py --page-slug stock-analysis
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_project_mcp_servers.py -q -k "stock_analysis or stock"
```

Expected: pass, with stock still non-certified.

**Acceptance Criteria:**

- `/stock-analysis` has a direct route lane.
- It cannot be misread as trading advice or formal metric certification.

### Task 6: Seed Trace Bundles For Visible Unseeded Routes

**Files:**

- Modify: `scripts/codex_page_readiness.py`
- Modify: `scripts/mcp/moss_project_mcp.py`
- Modify: `docs/page_contracts.md`
- Modify: `docs/metric_dictionary.md`
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_project_mcp_servers.py`

**Priority order:**

1. `/cross-asset`
2. `/decision-items`
3. `/average-balance`
4. `/bank-ledger-dashboard`
5. `/kpi`
6. `/cashflow-projection`

**Step 1: Write failing route-coverage tests**

Run:

```powershell
python -m pytest tests\test_codex_page_readiness_gate.py -q -k "visible_unseeded or route_scope"
```

Expected: fail for each route before it is seeded, or pass with explicit `not-started` if the current test already encodes the gap.

**Step 2: Seed one route at a time**

For each route:

- add direct page ID
- add primary business question
- add primary API if known
- add formal/candidate/observational boundary
- add residual gaps
- do not add fake golden samples

**Step 3: Verify route-scope**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_project_mcp_servers.py -q -k "route_scope or evidence_readiness"
```

Expected:

- visible unseeded count decreases only for routes actually seeded
- no route becomes certified by seeding alone

**Acceptance Criteria:**

- The system has fewer blind spots.
- Route-scope classification remains honest.

### Task 7: Run The Institutional Frontend Quality Pass Only After Evidence Boundaries Are Stable

**Files:**

- Inspect: `docs/frontend-institutional-standard.md`
- Inspect: `frontend/src/theme/designSystem.ts`
- Inspect: `frontend/src/theme/tokens.ts`
- Inspect: affected page CSS/modules
- Test: affected page tests under `frontend/src/test/`
- Browser: affected Playwright smoke/a11y checks

**Step 1: Pick one route per pass**

Use route order:

1. `/product-category-pnl`
2. `/ledger-pnl`
3. `/pnl-attribution`
4. `/bond-analysis`
5. `/stock-analysis`

**Step 2: Apply design skills in order**

Use these skills when the pass touches visible UI:

- `frontend-design` for page-level investment-bank decision cockpit quality
- `critique` for hierarchy and decision clarity
- `arrange` for spacing and scan rhythm
- `typeset` for typography
- `normalize` for design-system consistency
- `polish` for final alignment/detail pass
- `audit` for accessibility/performance/theming responsiveness
- `visual-verdict` for screenshot comparison when a reference exists

**Step 3: Verify visible behavior**

Run the narrow frontend suite for the changed route, then:

```powershell
cd frontend
npm run typecheck
npm run debt:audit
npm run build
```

Also run the page's browser smoke/a11y command when available.

**Acceptance Criteria:**

- First screen makes the main business conclusion obvious.
- Stale/fallback/no-data/loading/error states are visible.
- No text overlap, no horizontal overflow, no blocking console errors.
- Visual polish does not hide candidate/formal boundaries or metric uncertainty.

## Execution Recommendation

Next round should execute **Task 3: Build The Direct `/bond-analysis` Gate I Lane**.

Reason:

- `/product-category-pnl` is closest to certification but needs real human owner/golden/manual-audit closure.
- `/ledger-pnl` and `/pnl-attribution` are already technically refreshed but still owner-gated.
- `/bond-analysis` has a concrete Codex-actionable gap: direct contract, direct sample boundary, owner packet, readiness/MCP wiring, and focused tests.
- `/stock-analysis` should wait until bond because it is more policy-sensitive and must avoid trading-instruction language.

## Verification Before Any Completion Claim

Before saying a route is complete, run the relevant narrow checks and read the output:

```powershell
python scripts\codex_page_readiness.py --page-slug <page-slug>
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py -q -k "<page keyword>"
```

For a business-contract-certified claim, also require:

```powershell
python scripts\check_<route>_business_owner_approval.py --require-captured
```

Expected for currently open routes: strict approval checks fail until real owner approval is captured.

## Stop Conditions

Stop and report instead of promoting status when:

- owner/approver/date fields are placeholder or missing
- golden sample approval is `captured-awaiting-approval`
- manual audit closure is false
- governance write would be needed but is not authorized
- metric unit/date/sign/null semantics are ambiguous
- a route would need to borrow another route's contract, sample, or approval

## Plan Changelog

- Added route-scoped certification plan for the next top-investment-bank standard push.
- Chose `/bond-analysis` as the next Codex-actionable execution lane.
- Preserved the human-gated `/product-category-pnl` certification lane.
- Kept `/ledger-pnl`, `/pnl-attribution`, and `/stock-analysis` within non-certified boundaries.
