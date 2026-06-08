# Top Investment Bank Standard Next Certification Optimization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from strong institutional UI readiness to route-scoped top-investment-bank certification through evidence closure, business-owner approval, and final visual QA.

**Architecture:** Treat the standard as a certification operating system, not a styling pass. Each route advances through direct page contract, metric dictionary, golden sample, lineage/governance evidence, manual audit, owner approval, and browser-quality gates. Keep candidate, observational, DTO-only, and formal-use surfaces explicitly separated until real approval exists.

**Tech Stack:** Python readiness scripts, pytest, Markdown governance packets, golden sample fixtures, MOSS MCP fallback scripts, PowerShell readiness wrappers, frontend Vitest, browser smoke/a11y checks, typecheck, debt audit, Vite build, design audit skills.

---

## Current Assessment

As of the latest route-scope run:

- Total classified routes: `39`
- Seeded trace bundles: `30`
- Visible navigation routes: `36`
- Visible routes without seeded trace bundles: `9`
- `business-contract-certified`: `0`
- `evidence-pending`: `13`
- `gate-i-gap`: `1`
- `frontend-ready`: `6`
- `frontend-only`: `10`
- `not-started`: `9`

The target is not fully achieved yet. The frontend has strong flagship surfaces, but the business-certification layer is still open.

Allowed claim:

> MOSS has institutional-grade frontend surfaces and active certification lanes. Full top-investment-bank business certification remains route-scoped and pending.

Forbidden claim:

> MOSS, or any individual route, is fully top-investment-bank business-certified before direct golden approval, manual audit closure, and captured owner approval all exist.

## Definition Of Top Investment Bank Standard

A route reaches the target only when all gates below pass:

| Gate | Required proof |
| --- | --- |
| Primary business question | First screen answers one decision question clearly. |
| Metric traceability | API response -> adapter/transformer -> state/selector -> component -> chart/table is traced and tested. |
| Unit/date/null semantics | Units, precision, rounding, date basis, fallback/stale state, null vs zero, and currency scale are explicit. |
| Direct route contract | Page ID, route, primary API, decision scope, and formal/candidate boundary are route-specific. |
| Metric dictionary | Metric IDs and source rules are direct to the page or explicitly candidate/observational. |
| Golden sample | Route-scoped sample exists and approval metadata is non-placeholder. |
| Lineage/governance evidence | Source version, rule version, cache version, fallback/stale state, and governance record are reviewed. |
| Manual audit | Human audit closes page contract, metric dictionary, UI/API payload, sample, live smoke, and lineage checks. |
| Business-owner approval | Strict checker reports captured owner approval with real owner, approver, date, and acceptance fields. |
| Browser quality | Desktop/tablet/mobile pass smoke, a11y, overflow, loading/error/stale states, typecheck, debt audit, and build. |

## Strategy

1. Close machine-checkable evidence drift first.
2. Promote no route without human evidence.
3. Use `/product-category-pnl` as the first true certification candidate.
4. Use `/bond-analysis` to prove the direct route-lane pattern for formerly missing Gate I surfaces.
5. Use `/stock-analysis` next, but keep it observational and never convert it into trading instructions.
6. Only after evidence lanes are stable, run the top-tier UI/UX pass with browser screenshots and measurable a11y/responsive evidence.

## Task 1: Sync The Current `/bond-analysis` Evidence Lane

**Files:**

- Modify: `tests/golden_samples/README.md`
- Modify: `docs/golden_sample_catalog.md`
- Modify: `docs/golden_sample_plan.md`
- Modify: `docs/metric_dictionary.md`
- Modify: `tests/test_governance_doc_contract.py`
- Modify: `docs/audits/2026-06-06-route-scope-classification.md`
- Modify: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`

**Step 1: Update sample-count documentation**

Change capture-ready sample count from `15` to `16`, total sample directories from `16` to `17`, and add:

```text
GS-BOND-ANALYSIS-ACTION-ATTR-A
```

Expected: docs match the newly added sample directory.

**Step 2: Update the metric dictionary sample-scope matrix**

Add `GS-BOND-ANALYSIS-ACTION-ATTR-A` with:

```text
page_id: PAGE-BOND-ANALYSIS-001
metrics: MTR-BOND-ACT-001..006
status: capture-ready pending approval
formal_use_allowed: false
```

Expected: route remains evidence-pending, not certified.

**Step 3: Update governance doc test count**

Change the governance doc contract expected count from `16` to `17`, or derive it from the registered sample directories if that pattern stays small and reviewable.

Run:

```powershell
python -m pytest tests\test_governance_doc_contract.py::test_capture_ready_sample_count_stays_in_sync_across_docs_and_gate -q
```

Expected: pass.

**Step 4: Refresh route audit boards**

Update the boards to the current route-scope counts:

```text
route_count=39
seeded_trace_bundle_count=30
visible_unseeded_route_count=9
business_contract_certified_count=0
evidence_pending_count=13
gate_i_gap_count=1
frontend_ready_count=6
frontend_only_count=10
not_started_count=9
```

Expected:

- `/bond-analysis` moves from `gate-i-gap` to `evidence-pending`
- `/stock-analysis` remains the only `gate-i-gap`
- no route is marked `business-contract-certified`

**Step 5: Verify the lane**

Run:

```powershell
python -m pytest tests\test_governance_doc_contract.py tests\test_golden_sample_release_matrix.py -q
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_golden_samples_capture_ready.py -q -k "bond_analysis or bond or capture_ready_golden_sample_files_exist or capture_ready_golden_sample_metadata"
python scripts\codex_page_readiness.py --route-scope
```

Expected:

- governance docs are synchronized
- bond-analysis remains `evidence-pending`
- strict approval remains pending

## Task 2: Keep `/product-category-pnl` As The First Certification Candidate

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

**Step 1: Regenerate owner packets**

Run:

```powershell
python scripts\product_category_pnl_first_certification_packet.py
python scripts\product_category_pnl_owner_decision_packet.py
```

Expected:

- `business_contract_certified=false`
- blocker/action-item counts remain machine-consistent

**Step 2: Run the non-strict approval checker**

Run:

```powershell
python scripts\check_product_category_pnl_business_owner_approval.py
```

Expected:

- approval is pending
- owner action items remain visible

**Step 3: Run the strict checker as expected failure**

Run:

```powershell
python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected: fail until real owner approval is captured.

**Step 4: Verify packet consistency**

Run:

```powershell
python -m pytest tests\test_product_category_pnl_business_owner_approval_status.py tests\test_product_category_pnl_first_certification_packet.py tests\test_product_category_pnl_owner_decision_packet.py -q
```

Expected: pass.

**Acceptance Criteria:**

- `/product-category-pnl` remains the first human-gated certification lane.
- No generated document is treated as business-owner approval.
- The route is promoted only after strict checker passes with real approval metadata.

## Task 3: Close `/bond-analysis` From Evidence-Pending To Owner-Ready

**Files:**

- Inspect: `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/request.json`
- Inspect: `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/response.json`
- Inspect: `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/assertions.md`
- Inspect: `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/approval.md`
- Inspect: `docs/pnl/bond-analysis-owner-evidence-packet.md`
- Script: `scripts/check_bond_analysis_business_owner_approval.py`
- Script: `scripts/bond_analysis_owner_evidence_packet.py`
- Test: `tests/test_bond_analysis_business_owner_approval_status.py`
- Test: `tests/test_bond_analysis_owner_evidence_packet.py`

**Step 1: Regenerate the evidence packet**

Run:

```powershell
python scripts\bond_analysis_owner_evidence_packet.py
```

Expected:

- `business_contract_certified=false`
- `formal_use_allowed=false`
- approval remains pending

**Step 2: Verify strict approval failure**

Run:

```powershell
python scripts\check_bond_analysis_business_owner_approval.py --require-captured
```

Expected: fail until real owner approval exists.

**Step 3: Verify packet/checker tests**

Run:

```powershell
python -m pytest tests\test_bond_analysis_business_owner_approval_status.py tests\test_bond_analysis_owner_evidence_packet.py -q
```

Expected: pass.

**Acceptance Criteria:**

- `/bond-analysis` is not a Gate I structural gap anymore.
- It is owner-ready but not certified.
- It does not borrow `/bond-dashboard` contract, metrics, golden sample, or approval state.

## Task 4: Build The Direct `/stock-analysis` Gate I Lane

**Files:**

- Modify: `docs/page_contracts.md`
- Modify: `docs/metric_dictionary.md`
- Modify: `docs/golden_sample_catalog.md`
- Create: `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A/`
- Create: `docs/pnl/stock-analysis-business-owner-approval-template.md`
- Create: `docs/pnl/stock-analysis-owner-evidence-packet.md`
- Create: `scripts/check_stock_analysis_business_owner_approval.py`
- Create: `scripts/stock_analysis_owner_evidence_packet.py`
- Modify: `scripts/codex_page_readiness.py`
- Modify: `scripts/mcp/moss_project_mcp.py`
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_golden_samples_capture_ready.py`
- Test: `tests/test_project_mcp_servers.py`
- Create: `tests/test_stock_analysis_business_owner_approval_status.py`
- Create: `tests/test_stock_analysis_owner_evidence_packet.py`

**Step 1: Write failing boundary tests**

Tests must require:

- `/stock-analysis` has direct page ID evidence
- no formal trading-instruction claim exists
- sample is observational/candidate only
- `formal_use_allowed=false`
- owner approval is pending

Run:

```powershell
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_golden_samples_capture_ready.py -q -k "stock_analysis or stock"
```

Expected: fail before implementation.

**Step 2: Add direct observational contract**

Add a route-specific contract that states:

```text
route: /stock-analysis
boundary: observational analysis only
formal_use_allowed: false
not_trading_instruction: true
```

Expected: users can see evidence and caveats without confusing the page with formal investment advice.

**Step 3: Add capture-ready observational sample**

Create the sample directory with:

```text
request.json
response.json
assertions.md
approval.md
```

Expected: `approval.md` is `captured-awaiting-approval`, not approved.

**Step 4: Verify classification movement**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
```

Expected:

- `/stock-analysis` moves from `gate-i-gap` to `evidence-pending`
- `gate_i_gap_count=0`
- `business_contract_certified_count=0`

## Task 5: Seed Visible Business Routes Without Trace Bundles

**Files:**

- Modify: `docs/page_contracts.md`
- Modify: `docs/metric_dictionary.md`
- Modify: `scripts/codex_page_readiness.py`
- Test: `tests/test_codex_page_readiness_gate.py`

**Priority routes:**

1. `/decision-items`
2. `/average-balance`
3. `/bank-ledger-dashboard`
4. `/kpi`
5. `/cashflow-projection`
6. `/cross-asset`

**Step 1: Add direct seed trace bundles one route at a time**

Each route gets:

```text
page_id or explicit GAP id
route
primary business question
source endpoints
formal/candidate/observational boundary
visible no-data/stale/fallback rule
```

Expected: route moves from `not-started` to either `evidence-pending`, `frontend-ready`, or an explicit `gate-i-gap`.

**Step 2: Verify after each route**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py -q -k route_scope
```

Expected: no unclassified route and no false certification.

## Task 6: Run The Final Institutional UI/UX Quality Pass

**Files:**

- Inspect: `frontend/src/router/routes.tsx`
- Inspect: relevant page files under `frontend/src/features/`
- Inspect: `frontend/src/theme/`
- Modify only page-level or page-local style files needed for visible issues.

**Step 1: Audit the priority pages**

Run browser/a11y/responsive checks for:

```text
/product-category-pnl
/pnl-attribution
/ledger-pnl
/bond-analysis
/stock-analysis
```

Expected:

- no horizontal overflow at mobile/tablet/desktop widths
- no blocking console errors
- first screen conclusion is visible
- no stale/fallback state is hidden
- no generic decorative complexity that reduces decision clarity

**Step 2: Apply design skills only where evidence says the page needs it**

Use:

```text
frontend-design
ui-ux-pro-max
audit
adapt
arrange
typeset
polish
visual-verdict
```

Expected: visual changes improve scanability, hierarchy, data confidence, and review ergonomics.

**Step 3: Verify frontend checks**

Run from `frontend/`:

```powershell
npm.cmd run typecheck
npm.cmd run debt:audit
npm.cmd run build
```

Run targeted page tests/a11y commands already registered for the touched page.

Expected: pass.

## Completion Evidence

Before claiming completion, run:

```powershell
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_golden_samples_capture_ready.py tests\test_governance_doc_contract.py -q
```

Then run page-specific backend/frontend/browser checks for every route changed in the pass.

Final report must include:

- current certification counts
- routes moved between classifications
- routes still pending owner/golden/manual audit approval
- strict approval checkers that still fail by design
- frontend checks run
- residual risk from unavailable MCP servers or local fallback evidence

## Stop Conditions

Stop only when:

- requested route lane is verified complete, or
- a destructive or authorization-gated action is required, or
- real human approval is missing and the strict checker correctly blocks promotion.

Do not set:

```text
formal_use_allowed=true
closure_approved=true
business_owner_approval_captured=true
golden_sample_approved=true
```

unless real evidence exists.
