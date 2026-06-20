# Top Investment Bank Standard Continued Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from institutional-grade frontend plus evidence lanes to route-scoped top-investment-bank certification readiness without making false business-certification claims.

**Architecture:** Treat "top investment bank standard" as a controlled certification pipeline: route contract, metric dictionary, golden sample, lineage/governance evidence, manual audit, owner approval, and browser-quality evidence. Keep formal, candidate, DTO-only, observational, and frontend-only surfaces separated until real human approval exists.

**Tech Stack:** Python readiness scripts, pytest, Markdown governance packets, golden sample fixtures, local MOSS MCP fallback scripts, PowerShell page readiness wrappers, frontend Vitest, Playwright/a11y smoke checks, TypeScript typecheck, debt audit, Vite build, UI audit skills.

---

## Current Baseline

Fresh route-scope command:

```powershell
python scripts\codex_page_readiness.py --route-scope
```

Current counts:

```text
route_count=39
seeded_trace_bundle_count=37
visible_navigation_route_count=36
visible_unseeded_route_count=2
business_contract_certified_count=0
evidence_pending_count=21
gate_i_gap_count=0
frontend_ready_count=6
frontend_only_count=10
not_started_count=2
out_of_scope_count=0
unclassified_count=0
```

Current truth:

- `/stock-analysis` has moved from `gate-i-gap` to `evidence-pending`.
- `/average-balance` has moved from `not-started` to `evidence-pending` as a candidate ADB analytical lane.
- `/bank-ledger-dashboard` has moved from `not-started` to `evidence-pending` as a candidate ledger read-model lane for `/api/ledger/dashboard`; it has no golden sample, no direct approval, and must not be treated as formal PnL or formal balance truth.
- `/cashflow-projection` has moved from `not-started` to `evidence-pending` as a candidate liquidity projection lane for `/api/cashflow-projection`; it has no golden sample, no standalone PAGE/MTR approval, and must not be treated as formal liquidity, risk, balance, or PnL truth.
- `/concentration-monitor` has moved from `not-started` to `evidence-pending` as a candidate concentration-monitor lane for `/api/bond-analytics/credit-spread-migration`; it has no golden sample, no standalone PAGE/MTR approval, and must not be treated as formal risk truth or certified concentration-limit approval.
- `/team-performance` has moved from `not-started` to `evidence-pending` as a candidate team-performance mapping lane for `/api/pnl/by-business-ytd` with product-category context; it has no golden sample, no standalone PAGE/MTR approval, and must not be treated as formal KPI truth, formal PnL truth, or owner-approved performance allocation.
- No route is business-contract-certified.
- `business_contract_certified_count` must remain `0` until direct golden approval, manual audit closure, and captured business-owner approval all exist.
- The UI is not the main blocker anymore. The remaining blocker is governed evidence closure.

Allowed claim:

```text
MOSS has institutional-grade frontend surfaces and all current seeded routes have route-scope classification coverage. Full top-investment-bank business certification remains route-scoped and pending owner/golden/manual-audit closure.
```

Forbidden claim:

```text
MOSS, or any individual route, is fully top-investment-bank business-certified.
```

## Target Standard

A route reaches the top-investment-bank standard only when all of these are true:

| Gate | Proof required |
| --- | --- |
| Decision clarity | First screen answers one primary business question. |
| Metric correctness | API response -> adapter/transformer -> state/selector -> component -> chart/table is traced and tested. |
| Semantic rigor | Units, precision, rounding, date basis, stale/fallback state, null vs zero, and currency scale are explicit. |
| Direct route contract | Page ID, route, primary API, and formal/candidate/observational boundary are route-specific. |
| Golden sample | Route-scoped sample exists and approval metadata is non-placeholder. |
| Governance evidence | Source version, rule version, cache version, fallback/stale state, and review status are recorded. |
| Manual audit | Human audit closes page contract, metric dictionary, UI/API payload, sample, live smoke, and lineage checks. |
| Business-owner approval | Strict checker passes with real owner, approver, date, acceptance, and scope fields. |
| Browser quality | Desktop/tablet/mobile pass smoke, a11y, overflow, loading/error/stale states, typecheck, debt audit, and build. |

## Institutional UI Standard

Use a data-dense drill-down workbench model for the UI layer. Top-investment-bank quality here means a calm, high-density decision surface: first-screen conclusion, compact KPI hierarchy, traceable units/dates/source status, drill-down rows, hover/focus states, no horizontal overflow, no emoji icons, no decorative chart chrome, and visible empty/stale/fallback/error states.

Do not treat visual polish as certification. UI work can make a route flagship-ready, but route certification still requires direct contract, metric dictionary, golden sample approval, governance/manual audit closure, and captured business-owner approval.

## Task 1: Sync The Certification Boards To The New Route-Scope Baseline

**Files:**

- Modify: `docs/audits/2026-06-06-route-scope-classification.md`
- Modify: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`
- Inspect: `scripts/codex_page_readiness.py`
- Test: `tests/test_codex_page_readiness_gate.py`

**Step 1: Refresh the route-scope board**

Update the board counts to:

```text
seeded_trace_bundle_count=36
visible_unseeded_route_count=3
evidence_pending_count=20
gate_i_gap_count=0
not_started_count=3
business_contract_certified_count=0
```

Expected: `/stock-analysis` and `/kpi-performance` are no longer represented as unseeded or Gate I gaps; `/average-balance` is seeded as a candidate ADB analytical lane; `/bank-ledger-dashboard` is seeded as a candidate ledger read-model lane; `/cashflow-projection` is seeded as a candidate liquidity projection lane; `/concentration-monitor` is seeded as a candidate concentration-monitor lane. None of these promotions grants formal-use, golden, manual-audit, or owner-approval status.

**Step 2: Refresh the certification board**

Update the priority table so `/stock-analysis` is `evidence-pending`, observational only, and approval pending; `/bank-ledger-dashboard` is `evidence-pending`, candidate ledger read-model only, and approval pending; `/cashflow-projection` is `evidence-pending`, candidate liquidity projection only, and approval pending; and `/concentration-monitor` is `evidence-pending`, candidate concentration-monitor only, and approval pending.

Expected: board says the route lane exists, but does not certify trading instruction, formal PnL, formal balance truth, or formal use.

**Step 3: Verify route-scope consistency**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py -q
```

Expected: pass; `business_contract_certified_count=0`; `gate_i_gap_count=0`.

## Task 2: Finish `/stock-analysis` Evidence-Lane Synchronization

**Files:**

- Inspect: `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A/request.json`
- Inspect: `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A/response.json`
- Inspect: `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A/assertions.md`
- Inspect: `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A/approval.md`
- Modify: `docs/pnl/stock-analysis-owner-evidence-packet.md`
- Modify: `docs/golden_sample_catalog.md`
- Modify: `docs/golden_sample_plan.md`
- Modify: `docs/metric_dictionary.md`
- Modify: `tests/golden_samples/README.md`
- Modify: `tests/test_governance_doc_contract.py`
- Script: `scripts/check_stock_analysis_business_owner_approval.py`
- Script: `scripts/stock_analysis_owner_evidence_packet.py`
- Test: `tests/test_stock_analysis_business_owner_approval_status.py`
- Test: `tests/test_stock_analysis_owner_evidence_packet.py`
- Test: `tests/test_golden_samples_capture_ready.py`

**Step 1: Regenerate the owner packet**

Run:

```powershell
python scripts\stock_analysis_owner_evidence_packet.py
```

Expected:

- `business_contract_certified=false`
- `formal_use_allowed=false`
- `approval_status=pending`
- no trading-instruction claim exists

**Step 2: Verify strict approval blocks correctly**

Run:

```powershell
python scripts\check_stock_analysis_business_owner_approval.py --require-captured
```

Expected: fail until real owner approval exists.

**Step 3: Sync golden-sample documentation**

Add `GS-STOCK-ANALYSIS-OBS-A` to the sample catalog, sample plan, README, and metric dictionary sample-scope matrix.

Expected: capture-ready sample counts match the registered sample directories and tests.

**Step 4: Run focused stock checks**

Run:

```powershell
python -m pytest tests\test_stock_analysis_business_owner_approval_status.py tests\test_stock_analysis_owner_evidence_packet.py -q
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_golden_samples_capture_ready.py -q -k "stock_analysis or stock"
```

Expected: pass.

## Task 3: Keep `/product-category-pnl` As The First True Certification Candidate

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

**Step 1: Regenerate owner-facing packets**

Run:

```powershell
python scripts\product_category_pnl_first_certification_packet.py
python scripts\product_category_pnl_owner_decision_packet.py
```

Expected: blocker/action-item counts remain machine-consistent.

**Step 2: Run approval checkers**

Run:

```powershell
python scripts\check_product_category_pnl_business_owner_approval.py
python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected: non-strict checker reports pending; strict checker fails until real approval exists.

**Step 3: Verify packet consistency**

Run:

```powershell
python -m pytest tests\test_product_category_pnl_business_owner_approval_status.py tests\test_product_category_pnl_first_certification_packet.py tests\test_product_category_pnl_owner_decision_packet.py -q
```

Expected: pass.

## Task 4: Turn Evidence-Pending Routes Into Owner-Ready Lanes

**Route order:**

1. `/pnl-attribution`
2. `/ledger-pnl`
3. `/bond-analysis`
4. `/stock-analysis`

**Files:**

- Inspect route-specific `docs/pnl/*owner-evidence-packet.md`
- Inspect route-specific approval checkers under `scripts/check_*_business_owner_approval.py`
- Inspect route-specific packet generators under `scripts/*owner_evidence_packet.py`
- Inspect route-specific golden sample directories under `tests/golden_samples/`

**Step 1: Regenerate each packet**

Run the route-specific packet generator.

Expected: each packet is current and explicitly says pending approval where approval is missing.

**Step 2: Run strict checkers**

Run each route-specific checker with `--require-captured`.

Expected: strict failure remains by design until real owner approval exists.

**Step 3: Run focused tests**

Run each route's owner/checker tests.

Expected: tests pass; no route is certified.

## Task 5: Seed The Remaining Visible Unseeded Routes

**Priority routes:**

1. `/platform-config`
2. `/news-events`

Completed in the current evidence-seeding pass:

- `/bank-ledger-dashboard` now has a seeded candidate trace bundle for `/api/ledger/dashboard` plus supporting ledger date, position, and export APIs. It remains `evidence-pending`, has no golden sample, has no standalone PAGE/MTR approval, and must not be used as formal PnL or formal balance truth.
- `/cashflow-projection` now has a seeded candidate trace bundle for `/api/cashflow-projection` plus balance-analysis date support. It remains `evidence-pending`, has no golden sample, has no standalone PAGE/MTR approval, and must not be used as formal liquidity, risk, balance, or PnL truth.
- `/concentration-monitor` now has a seeded candidate trace bundle for `/api/bond-analytics/credit-spread-migration` plus bond-analytics date support. It remains `evidence-pending`, has no golden sample, has no standalone PAGE/MTR approval, and must not be used as formal risk truth or certified concentration-limit approval.
- `/team-performance` now has a seeded candidate trace bundle for `/api/pnl/by-business-ytd` plus product-category context. It remains `evidence-pending`, has no golden sample, has no standalone PAGE/MTR approval, and must not be used as formal KPI truth, formal PnL truth, or owner-approved performance allocation.

**Files:**

- Modify: `scripts/codex_page_readiness.py`
- Modify: `scripts/mcp/moss_project_mcp.py`
- Modify: `docs/page_contracts.md`
- Modify: `docs/metric_dictionary.md`
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_project_mcp_servers.py`

**Step 1: Add one route seed at a time**

Each seed must include:

```text
page_id or explicit GAP id
route
primary business question
source endpoints
formal/candidate/observational boundary
visible no-data/stale/fallback rule
run-supported commands if available
```

Expected: the route moves out of `not-started` without creating a false certification.

**Step 2: Verify after each route**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py -q
```

Expected: `visible_unseeded_route_count` decreases one route at a time.

## Task 6: Run The Final Institutional UI/UX Quality Pass

**Priority pages:**

1. `/product-category-pnl`
2. `/pnl-attribution`
3. `/ledger-pnl`
4. `/bond-analysis`
5. `/stock-analysis`
6. `/average-balance`
7. `/bank-ledger-dashboard`
8. `/cashflow-projection`
9. `/concentration-monitor`

**Skills/tools to use:**

- `frontend-design`
- `ui-ux-pro-max`
- `audit`
- `adapt`
- `arrange`
- `typeset`
- `polish`
- `visual-verdict`
- Playwright screenshot, console, a11y, and overflow checks

**Step 1: Capture browser evidence**

Check desktop, tablet, and mobile widths.

Expected:

- first-screen conclusion visible
- no horizontal overflow
- no blocking console errors
- loading, empty, stale, fallback, and error states visible
- no decorative complexity that hides the decision

**Step 2: Patch only evidence-backed issues**

Modify only page-level or page-local files needed for visible issues.

Expected: better scanability, hierarchy, density, trust signaling, and review ergonomics.

**Step 3: Verify frontend quality gates**

Run from `frontend/`:

```powershell
npm.cmd run typecheck
npm.cmd run debt:audit
npm.cmd run build
```

Run route-specific Vitest and Playwright checks for touched pages.

Expected: pass.

## Task 7: Produce The Certification Evidence Pack

**Files:**

- Modify: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`
- Create or modify: a final audit note under `docs/audits/`

**Step 1: Run completion checks**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_golden_samples_capture_ready.py tests\test_governance_doc_contract.py -q
```

Run page-specific backend/frontend/browser checks for every page touched in this plan.

**Step 2: Record the final state**

The final audit note must include:

- current certification counts
- routes moved between classifications
- routes still pending owner/golden/manual audit approval
- strict approval checkers that fail by design
- frontend checks run
- residual risk from unavailable MCP servers or local fallback evidence

Expected: the project can honestly say it is operating at an institutional certification discipline, while still refusing to claim business certification before real approval.

## Stop Conditions

Stop only when:

- the requested route lane is verified complete, or
- a destructive or authorization-gated action is required, or
- real human approval is missing and the strict checker correctly blocks promotion.

Never set the following without real evidence:

```text
formal_use_allowed=true
closure_approved=true
business_owner_approval_captured=true
golden_sample_approved=true
certified route status
```
