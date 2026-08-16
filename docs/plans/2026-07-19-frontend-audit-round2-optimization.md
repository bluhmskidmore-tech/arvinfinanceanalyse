# Frontend Audit Round-2 Optimization Plan

> Subagent-Driven Development execution plan. Supporting material only; AGENTS.md remains authority.

**Goal:** Close the next high-value leftovers from the 2026-07-19 frontend audit remediation: restore green mock-client tests, finish the cockpit “其他”桶 wiring, and close PnL bridge date/fallback result_meta.

**Architecture:** One page/workflow per task. No shared formal_result_runtime changes. No Phase 03 merge. No side-branch integration in this round.

**Tech Stack:** TypeScript/React (frontend), FastAPI/pytest (backend), Vitest.

---

## Scope

In:
1. Mock ApiClient lazy-load test regressions
2. Dashboard cockpit `merged_bucket_rows` production wiring
3. PnL bridge date/fallback metadata (caller-local only)

Out:
- `codex/balance-analysis-date-closure` merge
- Phase 03/04 adoption
- Bulk `raw_scale="ratio"` migration of all B-class callers
- Unrelated dirty worktree market/risk/home/agent changes

## Task 1: Fix mock ApiClient lazy-load test regressions

**Tier:** Tier 3 shared client plumbing, but scoped to mock-mode test correctness.

**Problem:** After mock composition was moved behind `lazyMockClientPromise` + Proxy in `frontend/src/api/client.ts` / `mockApiClient.ts`, these fail stably:
- `src/test/ApiClient.test.ts` (manual-adjustment created_at filter; eventType timeline filter) — shared singleton leaks state across tests
- `src/test/BondDashboardBundleClient.test.ts` — mock bundle sections resolve to `undefined`
- `src/test/BondAnalyticsInstitutionalCockpit.test.tsx` — multiple waits time out waiting for mock data

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify if needed: `frontend/src/api/mockApiClient.ts`
- Modify only if tests need reset helpers: the three failing test files above
- Do not modify: real-mode clients, domain mock payloads, unrelated pages

**Acceptance:**
1. Each `createApiClient({ mode: "mock" })` call gets an isolated mock composition (no cross-test state leak), OR tests can explicitly reset the lazy cache between cases.
2. Bond dashboard mock bundle sections assemble to the same envelopes as before the lazy split.
3. Targeted tests pass:
   - `npm run test -- --run src/test/ApiClient.test.ts src/test/BondDashboardBundleClient.test.ts src/test/BondAnalyticsInstitutionalCockpit.test.tsx`
4. `npm run typecheck` and `npm run debt:audit` pass; `client.ts` lines/mock counts do not grow over baseline.

**Not required:** production bundle size improvements beyond restoring correctness; no rename of mock modules.

## Task 2: Wire cockpit “其他”桶 to backend `merged_bucket_rows`

**Tier:** Tier 2 page-local display.

**Problem:** Backend already emits `merged_bucket_rows` on `/api/pnl/by-business-analysis` (`dimension=bond_bucket`) via `pnl_bond_bucket_merge.py`. Frontend `dashboardCockpitModel.ts` already reads `bondBucketMergedRows` when provided, but the production data path (`useDashboardData` / dashboard API adapter) may not pass `payload.merged_bucket_rows` through.

**Files:**
- Inspect/modify: `frontend/src/features/workbench/dashboard/services/dashboardApi.ts` (or the actual getBondBucketYield caller)
- Inspect/modify: any adapter that maps `PnlByBusinessAnalysisPayload` → cockpit model input
- Test: `frontend/src/features/workbench/dashboard/dashboardCockpitModel.test.ts` and/or the dashboard data hook/adapter test
- Do not modify: backend merge formula, `pnl_service.py` beyond already-shipped field

**Acceptance (revised 2026-07-19 after discovery):**
1. Add a tested adapter that maps `merged_bucket_rows` → `bondBucketMergedRows` with no local weighted recompute.
2. Wire that adapter into `useDashboardData` so any future cockpit consumer receives the field from the bond_bucket analysis payload.
3. When the field is present, `buildDashboardCockpitModel` “其他” ytm uses the backend merged annualized yield; when absent, `--`.
4. Targeted frontend tests pass; no debt:audit growth.

**Out of scope / residual:** `buildDashboardCockpitModel` and `useDashboardData` currently have **no production page consumer** (homepage is guarded against `useDashboardData`). Restoring a live cockpit page is a separate product task, not part of this seam-closure task.

## Task 3: PnL bridge date/fallback result_meta closure

**Tier:** Tier 2 caller-local backend.

**Problem:** `backend/app/services/pnl_bridge_service.py` builds result_meta but does not yet expose requested/resolved/as_of/fallback dates consistently; fallback severity may not merge into final quality_flag. This is the STATE.md “next real code work”.

**Contract gate (must confirm from existing contracts/lineage before coding):**

| Field | Source of truth |
|---|---|
| requested_report_date | request business report date |
| resolved_report_date | actual snapshot date used |
| as_of_date | same as resolved unless contract says otherwise |
| fallback_date | only when resolved ≠ requested; never invent across multi-curve |
| quality_flag | merge existing summary quality with fallback severity per approved matrix |

**Files:**
- Modify: `backend/app/services/pnl_bridge_service.py` (~L213 builder)
- Test: `tests/test_pnl_api_contract.py` (pnl_bridge cases) and/or focused new test
- Do not modify: `formal_result_runtime.py`, `result_meta.py` schema

**Acceptance:**
1. Tests cover: no fallback; latest-snapshot fallback; vendor unavailable.
2. Assertions include requested/resolved/as_of/fallback_date + quality_flag/vendor_status/fallback_mode.
3. `pytest tests/test_pnl_api_contract.py -q -k "pnl_bridge"` passes.
4. If contract evidence for multi-source fallback dates is missing, stop and report BLOCK — do not guess.

---

## Round 3 (appended 2026-07-19 PM)

### Task 4: Tighten PnL bridge quality-merge tests (follow-up from Task 3 quality review)

**Tier:** test/backend caller-local; behavior-preserving except explicitness.

**Files:**
- Modify: `tests/test_pnl_bridge_result_meta_dates.py`
- Modify: `backend/app/services/pnl_bridge_service.py` (comment + `fallback_date=None` explicitness only; no behavior change)

**Acceptance:**
1. latest_snapshot test asserts `summary_quality != "error"` and `meta.quality_flag == "stale"` (no soft branch).
2. New direct unit test of `_merge_bridge_quality_flag` covering the full matrix (ok/warning/stale/error × latest_fallback true/false).
3. `fallback_date` is passed as literal `None` with a one-line comment that business report_date has no fallback per PAGE-BRIDGE-001; add a comment near the vendor_unavailable branch documenting the mixed vendor_unavailable+latest_snapshot residual as intended.
4. `pytest tests/test_pnl_bridge_result_meta_dates.py tests/test_pnl_api_contract.py -q -k "pnl_bridge or result_meta_dates"` passes; behavior identical.

### Task 5: Migrate B-class ratio callers to explicit `raw_scale="ratio"`

**Tier:** Tier 3 shared-schema consumers, additive param usage only.

**Problem:** `_normalize_numeric_raw` auto heuristic divides by 100 any pct raw with abs>1. B-class callers pass decimal ratios; dirty data >1 (a true >100% ratio) gets silently mis-divided. `raw_scale="ratio"` param already exists (default "auto" unchanged).

**Files (callers to migrate; do not touch pnl_attribution_service or executive_service):**
- `backend/app/services/bond_dashboard_service.py` (+ its repo-level pct constructions if that is where numeric_from_raw is called)
- `backend/app/services/liability_analytics_service.py` / `backend/app/core_finance/liability_analytics_compat.py`
- `backend/app/services/cashflow_projection_service.py`
- `backend/app/services/risk_scenario_stress_service.py`
- Tests colocated per module

**Acceptance:**
1. Each migrated call site declares `raw_scale="ratio"`.
2. Per-module tests cover: ratio 0.4 → "40%"-family display unchanged; ratio 1.5 → stays 150% (not 1.5%); 0/None unchanged.
3. Existing module/golden tests pass unchanged for in-contract data.
4. Do not modify `common_numeric.py` behavior.

### Task 6: Fix `mocks/pnlAttributionWorkbench.ts` pct-unit contract drift

**Tier:** Tier 2 mock-local.

**Problem:** mock uses `rp()` (unit "ratio") for fields whose backend contract is unit "pct" (e.g. `*_contribution_pct`), bypassing pct semantics the components now rely on.

**Files:**
- Modify: `frontend/src/mocks/pnlAttributionWorkbench.ts`
- Update affected component/page tests only if their fixtures rely on the wrong unit

**Acceptance:**
1. Fields contracted as pct Numeric use unit "pct" with decimal-ratio raw and unchanged display strings.
2. Targeted vitest for pnl-attribution components/pages pass; `npm run typecheck`; `npm run debt:audit` no growth.
3. Rendered mock-mode percentages unchanged (display parity is the equivalence bar).

### Task 7: Converge `PnLCompositionChart.tsx` inline styles into a CSS module

**Tier:** Tier 1 visual-only.

**Files:**
- Modify: `frontend/src/features/pnl-attribution/components/PnLCompositionChart.tsx`
- Create: colocated `.module.css` (or reuse an existing pnl-attribution styles module if one fits)
- Tests: existing `PnlCompositionChart.test.tsx` / `.states.test.tsx` keep passing

**Acceptance:**
1. Repeated static `style={{...}}` blocks move to CSS classes; only truly dynamic values (tone colors, chart heights) stay inline.
2. Visual semantics unchanged (class-for-style swap; DESIGN.md tokens preserved via existing designTokens or CSS vars).
3. `npm run test -- --run src/test/PnlCompositionChart.test.tsx src/features/pnl-attribution/components/PnLCompositionChart.states.test.tsx`, `npm run typecheck`, `npm run debt:audit` pass with TSX style-prop counts reduced (baseline may be lowered, never raised).

---

## Execution rules for subagents

- Work from repo root `f:\MOSS-V3`.
- Minimal diffs; do not touch unrelated dirty files.
- Do **not** git commit unless the controller explicitly says so (user has not requested commits).
- Prefer failing tests first, then fix.
- After each task: targeted tests + typecheck/debt where frontend touched.
