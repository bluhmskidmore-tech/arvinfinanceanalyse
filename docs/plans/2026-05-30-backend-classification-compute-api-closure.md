# Backend Classification And Compute API Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the backend "data classification and calculation API" question with an evidence-backed completion matrix and verification pass, then route any out-of-scope gaps to separate explicitly authorized lanes.

**Architecture:** Keep the existing layered direction: frontend -> API routes -> services -> repositories/core_finance/governance -> storage. Formal finance formulas stay in `backend/app/core_finance/`; API routes stay thin; DuckDB writes stay in `backend/app/tasks/`. This plan may verify and document excluded surfaces, but it must not implement or promote them unless a separate lane explicitly authorizes that work.

**Tech Stack:** Python, FastAPI, Pydantic schemas, DuckDB repositories/materializers, pytest, existing governance docs and backend release suite.

---

## Current Evidence Baseline

- `backend/app/AGENTS.md:5-15` defines repo-wide Phase 2 only for the formal-compute mainline: formal balance, formal PnL, formal FX, formal yield curve, PnL bridge, risk tensor, and core bond-analytics formal read surfaces.
- `backend/app/AGENTS.md:19-41` explicitly excludes `source_preview`, `qdb_gl_monthly_analysis`, market-data preview/vendor/analytical surfaces, `liability_analytics_compat`, cube-query, Agent, and other Phase 3 / Phase 4 expansion items.
- `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md:14-24` says repo-wide Phase 2 does not mean every page, workbench, or later analytical surface is open.
- `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md:131-160` lists supported governed balance workbook sections and explicitly keeps `advanced_attribution_bundle` outside the completed governed workbook.
- `backend/app/api/routes/source_preview.py:24-42` keeps source preview HTTP gated and reserved by default.
- `backend/app/core_finance/qdb_gl_monthly_analysis.py:135-137` marks formal financial indicators as `formal_pending` where governed production sources are not connected.

## Decision

Treat "finished" as a scoped release claim, not a whole-repo claim.

1. First create a backend route/functionality completion matrix.
2. Then verify the governed formal-compute mainline with targeted checks that match the matrix.
3. If a gap is inside the governed formal-compute mainline and already source-backed, close it as a bounded follow-up task with its own test.
4. If a gap belongs to an excluded surface, write only a separate lane handoff in this plan; do not implement it here.
5. Keep preview, vendor, compatibility, and source-missing workflows explicit rather than silently promoting them.

## Non-Goals

- Do not promote `source_preview` into formal truth.
- Do not implement `qdb_gl_monthly_analysis` formula changes under this plan; QDB GL is currently an excluded analytical-only / compatibility module and needs a named lane before code changes.
- Do not implement `advanced_attribution_bundle` as a balance-analysis workbook section.
- Do not convert `formal_pending` financial indicators to zero or mock values.
- Do not refactor auth, task queues, global SDK wrappers, database schema, or frontend architecture.
- Do not broaden the backend release definition without updating authority docs and tests.

## Phase 0: Completion Matrix And Boundary Lock

### Task 0.1: Add A Backend Completion Matrix Document

**Files:**
- Create: `docs/backend_classification_compute_api_closure.md`
- Read: `backend/app/AGENTS.md`
- Read: `docs/DOCUMENT_AUTHORITY.md`
- Read: `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md`
- Read: `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`
- Read: `scripts/backend_release_suite.py`

**Step 1: Draft the matrix**

Create a table with these columns:

```markdown
| Area | Representative APIs | Status | Formal scope? | Evidence | Next action |
| --- | --- | --- | --- | --- | --- |
```

Required rows:

- formal balance / balance-analysis
- formal PnL
- product-category PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal reads
- source preview
- qdb GL monthly analysis
- advanced attribution bundle
- market-data preview/vendor surfaces
- cube-query / liability compatibility / Agent

**Step 2: Use strict status labels**

Allowed labels only:

- `complete-in-scope`
- `complete-with-explicit-boundary`
- `candidate-source-backed-gap`
- `explicit-pending-source`
- `reserved-or-excluded`
- `unknown-needs-evidence`

**Step 3: Run a docs grep to catch accidental overclaims**

Run:

```powershell
rg -n "全部完成|全部开发完|all complete|everything is live|已全部" docs backend .planning
```

Expected: any broad completion phrase is either absent or scoped with Phase 2 / explicit exclusions.

### Task 0.2: Add A Contract Test For The Matrix Vocabulary

**Files:**
- Create: `tests/test_backend_classification_compute_closure_doc.py`
- Test: `docs/backend_classification_compute_api_closure.md`

**Step 1: Write the failing test**

Test that:

- the document exists
- every required area appears
- no unsupported status label appears
- excluded areas are not marked `complete-in-scope`
- `advanced_attribution_bundle` is not marked complete
- `source_preview` is not marked formal
- `qdb_gl_monthly_analysis` retains pending/source-gap semantics

**Step 2: Run the test**

Run:

```powershell
python -m pytest tests/test_backend_classification_compute_closure_doc.py -q
```

Expected before doc completion: FAIL on missing or incomplete matrix.

**Step 3: Complete the document and rerun**

Expected after completion: PASS.

## Phase 1: Formal Mainline Verification Pass

### Task 1.1: Verify Current Release Gate

**Files:**
- Existing: `scripts/backend_release_suite.py`
- Existing tests named in `RELEASE_SUITE_TESTS`

**Step 1: Run the canonical backend gate**

Run:

```powershell
python scripts/backend_release_suite.py --governance-audit-output governance-lineage-audit.json
```

Expected: PASS. If it fails, classify the failure by area before making any code changes.

### Task 1.2: Verify Mainline Areas Not Fully Covered By The Release Gate

**Files:**
- Existing: `tests/test_product_category_pnl_flow.py`
- Existing: `tests/test_product_category_formula_boundaries.py`
- Existing: `tests/test_balance_analysis_api.py`
- Existing: `tests/test_balance_analysis_workbook_contract.py`
- Existing: `tests/test_balance_analysis_materialize_flow.py`
- Existing: `tests/test_fx_mid_materialize.py`
- Existing: `tests/test_fx_analytical_view_api.py`
- Existing: `tests/test_yield_curve_materialize.py`
- Existing: `tests/test_yield_curve_term_structure_api.py`
- Existing: `tests/test_pnl_bridge_core.py`
- Existing: `tests/test_pnl_bridge_service_boundaries.py`
- Existing: `tests/test_risk_tensor_api.py`
- Existing: `tests/test_risk_tensor_core.py`
- Existing: `tests/test_bond_analytics_api.py`
- Existing: `tests/test_bond_analytics_service.py`

**Step 1: Run targeted product-category checks**

Run:

```powershell
python -m pytest tests/test_product_category_pnl_flow.py tests/test_product_category_formula_boundaries.py tests/test_result_meta_on_all_ui_endpoints.py -q
```

Expected: PASS for formal/scenario separation, refresh status, YTD fallback behavior, and result meta.

**Step 2: Run targeted balance-analysis checks**

Run:

```powershell
python -m pytest tests/test_balance_analysis_api.py tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_materialize_flow.py -q
```

Expected: PASS, including the guard that `advanced_attribution_bundle` is not silently exposed.

**Step 3: Run targeted formal FX and yield-curve checks**

Run:

```powershell
python -m pytest tests/test_fx_mid_materialize.py tests/test_fx_analytical_view_api.py tests/test_yield_curve_materialize.py tests/test_yield_curve_term_structure_api.py -q
```

Expected: PASS for materialized formal FX/yield-curve paths and outward API contracts.

**Step 4: Run targeted PnL bridge, risk tensor, and bond-analytics checks**

Run:

```powershell
python -m pytest tests/test_pnl_bridge_core.py tests/test_pnl_bridge_service_boundaries.py tests/test_risk_tensor_api.py tests/test_risk_tensor_core.py tests/test_bond_analytics_api.py tests/test_bond_analytics_service.py -q
```

Expected: PASS for the remaining in-scope formal-compute mainline rows in the completion matrix.

## Phase 2: Product-Category And Classification Source Truth Tightening

### Task 2.1: Guard Product-Category Calculation Ownership

**Files:**
- Read/possibly modify: `backend/app/core_finance/product_category_pnl.py`
- Read/possibly modify: `backend/app/services/product_category_pnl_service.py`
- Read/possibly modify: `backend/app/api/routes/product_category_pnl.py`
- Test: `tests/test_product_category_pnl_flow.py`
- Test: `tests/test_product_category_formula_boundaries.py` if present; otherwise create the smallest equivalent test.

**Step 1: Add or tighten a boundary test**

Assert that product-category formulas live in `core_finance/product_category_pnl.py`, while the route only validates query params and delegates to service.

**Step 2: Run the targeted tests**

Run:

```powershell
python -m pytest tests/test_product_category_pnl_flow.py tests/test_product_category_formula_boundaries.py -q
```

Expected: PASS. If `test_product_category_formula_boundaries.py` does not exist, create a focused test rather than a repo-wide scanner.

### Task 2.2: Separate Preview Classification From Formal Classification

**Files:**
- Read: `backend/app/services/source_rules.py`
- Read: `backend/app/core_finance/zqtz_asset_bond_category.py`
- Read: `backend/app/api/routes/source_preview.py`
- Test: `tests/test_result_meta_on_all_ui_endpoints.py`
- Test: `tests/test_source_rule_foundation.py`
- Test: `tests/test_zqtz_asset_bond_category.py`

**Step 1: Add explicit doc text to the completion matrix**

State that `source_rules.py` powers preview/foundation classification and is not formal truth.

**Step 2: Use existing fail-closed tests before adding any new preview-flow coverage**

Prefer the existing fail-closed assertions in `tests/test_result_meta_on_all_ui_endpoints.py`. Add a new regression test only if the matrix/doc currently permits confusion.

If a new test is needed, it should assert only:

- `source_preview` remains reserved by default.
- formal ZQTZ asset bond display classification is covered by `core_finance/zqtz_asset_bond_category.py`.

Do not modify `source_rules.py` or run the full preview implementation flow as part of this closure unless a separate preview lane is authorized.

**Step 3: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_result_meta_on_all_ui_endpoints.py tests/test_source_rule_foundation.py tests/test_zqtz_asset_bond_category.py -q
```

Expected: PASS without promoting preview APIs into formal scope.

## Phase 3: Deferred Lane Handoffs For Out-Of-Scope Gaps

### Task 3.1: QDB GL Formal-Pending Lane Handoff

**Files:**
- Existing plan: `docs/plans/2026-05-06-qdb-gl-financial-indicator-rule-split.md`
- Read: `backend/app/core_finance/qdb_gl_monthly_analysis.py`
- Read: `backend/app/services/qdb_gl_monthly_analysis_service.py`
- Reference test for the separate QDB GL lane: `tests/test_qdb_gl_monthly_analysis_core.py`
- Reference test for the separate QDB GL lane: `tests/test_qdb_gl_monthly_analysis_api.py`

**Step 1: Mark QDB GL as excluded in the completion matrix**

The matrix row for `qdb_gl_monthly_analysis` must not use `complete-in-scope`. Use one of:

- `explicit-pending-source` when discussing formal financial indicators with missing governed production sources.
- `reserved-or-excluded` when discussing the route/workflow as part of repo-wide Phase 2.

**Step 2: Record the separate lane entry**

In the matrix `Next action` cell, link to `docs/plans/2026-05-06-qdb-gl-financial-indicator-rule-split.md` and state that implementation requires a named QDB GL lane.

If that separate lane is later authorized, its first step should classify each QDB financial indicator as:

- source-backed and computable from QDB GL/monthly inputs
- candidate but not formal
- formal pending source

**Step 3: Do not change QDB GL formulas in this plan**

This plan may inspect QDB GL code/docs for evidence. It must not edit `backend/app/core_finance/qdb_gl_monthly_analysis.py` or `backend/app/services/qdb_gl_monthly_analysis_service.py`.

### Task 3.2: Advanced Attribution Boundary Handoff

**Files:**
- Existing boundary: `docs/plans/2026-04-12-advanced-attribution-implementation-plan.md`
- Existing boundary: `docs/plans/2026-04-12-balance-analysis-advanced-attribution-boundary.md`
- Read: `backend/app/services/advanced_attribution_service.py`
- Read: `backend/app/services/bond_analytics_service.py`
- Test: `tests/test_advanced_attribution_contract.py`
- Test: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Keep it outside balance-analysis workbook**

Do not add `advanced_attribution_bundle` to `/ui/balance-analysis/workbook`.

**Step 2: Mark the current state as explicit boundary, not completion**

The completion matrix should state that advanced attribution is outside the governed balance workbook. If a future lane implements a separate analytical envelope, it must use explicit `not_ready` warnings whenever required curve, bridge, and return-decomposition inputs are missing.

**Step 3: Run tests**

Run:

```powershell
python -m pytest tests/test_advanced_attribution_contract.py tests/test_balance_analysis_workbook_contract.py tests/test_bond_analytics_service.py -q
```

Expected: PASS. No silent zero-filled attribution should masquerade as formal truth.

## Phase 4: Release Claim And Go/No-Go

### Task 4.1: Re-run The Release Gate

**Files:**
- Existing: `scripts/backend_release_suite.py`
- Existing output: `governance-lineage-audit.json`

Run:

```powershell
python scripts/backend_release_suite.py --governance-audit-output governance-lineage-audit.json
```

Expected: PASS.

### Task 4.2: Update The Final Claim

**Files:**
- Modify: `docs/backend_classification_compute_api_closure.md`
- Possibly modify: `docs/V3_CUTOFF_EXIT_CRITERIA.md` only if the release boundary changed.
- Do not modify authority docs if the implementation only confirms current boundaries.

Final wording should be:

```text
Backend governed Phase 2 formal-compute mainline is complete for the listed in-scope routes.
Excluded preview/vendor/compatibility/Phase 3+ surfaces remain explicit reserved, pending, or analytical-only.
```

Do not write:

```text
Backend data classification and calculation APIs are all complete.
```

## Acceptance Criteria

- `docs/backend_classification_compute_api_closure.md` exists and lists every required backend area.
- The matrix uses only the allowed status labels.
- No excluded surface is marked as `complete-in-scope`.
- Product-category PnL remains backed by `backend/app/core_finance/product_category_pnl.py`, service orchestration, task materialization, and route delegation.
- Source preview remains reserved/gated and is not promoted to formal truth.
- QDB GL implementation is not changed by this plan; it is documented as a separate named lane.
- QDB GL formal-pending metrics remain null/pending until governed production sources exist.
- `advanced_attribution_bundle` remains outside the governed balance-analysis workbook.
- Targeted tests for every touched slice pass.
- `python scripts/backend_release_suite.py --governance-audit-output governance-lineage-audit.json` passes before claiming release closure.

## Recommended Execution Order

1. Execute Phase 0 first. It is the cheapest way to prevent scope confusion.
2. Execute Phase 1 immediately after to establish the current green/red baseline.
3. Execute Phase 2 only where the matrix/doc would otherwise confuse preview classification with formal classification.
4. Execute Phase 3 as handoff documentation only; do not implement QDB GL or advanced attribution code in this plan.
5. Treat `source_preview` promotion as a separate preview-lane project, not part of this closure.

## Remaining Risks

- MCP project servers were not exposed in the current Codex tool list during this planning pass, so the plan is grounded in repository code/docs/tests. Before changing metric formulas, use `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus` if they are available in the execution session.
- The worktree is currently dirty with many unrelated changes. Execution must preserve them and avoid broad formatting or unrelated cleanup.
- The phrase "classification API" may refer to preview source classification or formal business classification. This plan deliberately separates them to avoid accidental promotion.
