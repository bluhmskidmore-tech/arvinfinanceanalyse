# Frontend Audit Round-3 Optimization Plan

> Subagent-Driven Development. Supporting only; AGENTS.md remains authority.

**Goal:** Close the next leftovers after Round-2: yield-curve result_meta date provenance, PnL Bridge first-screen meta banner, and harden bridge quality-merge tests. Update planning STATE so “next code work” is no longer the already-done bridge meta task.

**Out:** side-branch merge, Phase 03, live cockpit page restore, bulk raw_scale B-class migration.

---

## Task 1: Yield curve term-structure result_meta dates

**Tier:** Tier 2 caller-local backend.

**Problem:** `yield_curve_term_structure_service.py` sets `fallback_mode` / `quality_flag=stale` but does **not** populate `requested_report_date` / `resolved_report_date` / `as_of_date` / `fallback_date` on result_meta (see builder ~L233–263).

**Contract gate (must confirm before coding):**
- Single curve or all curves resolve to the **same** trade_date → may set resolved/as_of to that date; fallback_date only when ≠ requested.
- Multiple curves resolve to **different** trade_dates → do **not** invent a single resolved/fallback_date; keep date fields null (or omit) and rely on per-curve `trade_date_resolved` + envelope `fallback_mode`/`quality_flag`. Cite `docs/page_contracts.md` / existing yield-curve tests.

**Files:**
- Modify: `backend/app/services/yield_curve_term_structure_service.py`
- Test: `tests/test_yield_curve_term_structure_api.py` (and/or focused new test)
- Do not modify: `formal_result_runtime.py`, `result_meta.py`

**Acceptance:**
1. Tests: exact date (no fallback); single-curve latest_snapshot fallback with dates; multi-curve divergent fallback dates do not fabricate one fallback_date.
2. Assertions include quality_flag / vendor_status / fallback_mode + the date fields per matrix.
3. `pytest tests/test_yield_curve_term_structure_api.py -q` passes.

## Task 2: PnL Bridge page first-screen stale/fallback banner

**Tier:** Tier 2 page-local display.

**Problem:** Round-2 backend now sets `result_meta.quality_flag=stale` / `fallback_mode=latest_snapshot` for curve fallback. `adaptPnlBridge` already maps this to adapter `state`. The page still highlights KPI via `summary.quality_flag` (often still `ok`), so users may miss envelope-level stale/fallback.

**Files:**
- Modify: `frontend/src/features/pnl/PnlBridgePage.tsx` (and CSS module if needed)
- Test: existing PnlBridge page/adapter tests under `frontend/src/test/` or colocated
- Do not modify: backend bridge service; do not reintroduce local finance calc

**Acceptance:**
1. When adapter state is `stale` or `fallback` (from result_meta), show a first-screen warning banner (Alert) above the KPI/waterfall with clear copy (回退/偏旧 + fallback_mode or dates if present).
2. When meta is healthy, banner absent.
3. KPI may still show summary.quality_flag; banner is the decision-level signal.
4. Targeted Vitest + typecheck + debt:audit (no style baseline growth).

## Task 3: Harden PnL bridge quality-merge tests + STATE sync

**Tier:** Test + planning docs.

**Problem:** Round-2 quality review noted `test_pnl_bridge_result_meta_dates.py` latest_snapshot quality assertion is soft; `_merge_bridge_quality_flag` lacks a pure matrix unit test. `.planning/STATE.md` still lists “PnL bridge backend date/fallback metadata closure” as pending next code work though Round-2 completed it.

**Files:**
- Modify: `tests/test_pnl_bridge_result_meta_dates.py` (and/or small unit tests for `_merge_bridge_quality_flag`)
- Modify: `.planning/STATE.md` (next actions: mark bridge done; point next code work to yield-curve meta / Round-3)
- Do not modify production bridge logic unless a test reveals a real bug

**Acceptance:**
1. Explicit assertion: latest_snapshot with summary ok → meta quality_flag == `"stale"`.
2. Pure matrix coverage for merge helper: ok/warning/error × latest_fallback true/false.
3. STATE.md next-actions updated so bridge is recorded complete; yield-curve meta / Round-3 listed as current code focus.
4. Related pytest passes.

---

## Execution rules

- Work from `f:\MOSS-V3`
- Minimal diffs; ignore unrelated dirty worktree files
- Do **not** git commit unless controller asks
- One implementer at a time; spec review then quality review per task
