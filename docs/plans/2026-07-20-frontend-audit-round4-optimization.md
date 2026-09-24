# Frontend Audit Round-4 Optimization Plan

> Subagent-Driven Development. Supporting only; AGENTS.md remains authority.

**Goal:** Close the next audit leftovers: PnL Bridge double-banner denoise, executive dashboard pct raw-scale inconsistency, and harden the shared `_NUMERIC_FIELDS` promote path against the legacy `raw_scale="auto"` heuristic.

**Out:** side-branch merge, Phase 03, live cockpit page restore, yieldAnalysis P1-10 sink (owner decision pending), macro-toolkit in-flight worktree files.

**Status (2026-07-20):**
| Task | Result |
|------|--------|
| T1 PnL Bridge double-banner | DONE — Spec PASS / Quality APPROVE |
| T2 Executive credit pct raw | DONE — Spec PASS / Quality APPROVE |
| T3 shared `_NUMERIC_FIELDS` promote | CANCELLED — GitNexus CRITICAL; no live sub-1pp bug via promote path. Do not land concurrent `explicit_numeric` / cashflow / liability dirty patches as Task 3. |
| T4 Positions first-screen state closure (replaces T3) | DONE — Spec PASS / Quality APPROVE |
| Final integrative review | READY TO COMMIT (scoped stage only; see Execution notes) |

---

## Task 1: PnL Bridge summary double-banner denoise

**Tier:** Tier 2 page-local display.

**Problem:** Round-3 added the first-screen decision-level Alert (`pnl-bridge-meta-banner`). When adapter state is `stale`/`fallback`, the summary `DataSection` still renders its own inner banner (`data-section-stale-banner` / `data-section-fallback-banner`), so the summary block shows two warning strips with overlapping copy. Detail section keeps its DataSection banner (it is that section's only signal).

**Files:**
- Modify: `frontend/src/features/pnl/PnlBridgePage.tsx`; `frontend/src/components/DataSection.tsx` ONLY if a suppress prop is the cleanest seam (opt-in, default unchanged)
- Test: `frontend/src/test/PnlBridgePage.test.tsx`
- Do not modify: adapter, backend

**Acceptance:**
1. stale/fallback: first-screen Alert present; summary DataSection inner banner absent; detail DataSection banner unchanged.
2. Healthy: no banners anywhere (unchanged).
3. If DataSection gains a prop, it is opt-in with default previous behavior and no other call sites change.
4. Targeted Vitest + typecheck pass; debt:audit no growth.

## Task 2: Executive risk-signal pct raw scale fix

**Tier:** Tier 2 caller-local backend.

**Problem:** `backend/app/services/executive_service.py` (~L2486) builds `Numeric(raw=cred_f, unit="pct", display=f"{cred_f:.1f}%", ...)`. Display implies `cred_f` is percent-points; storing the same value in `raw` violates the pct contract (raw must be decimal ratio, cf. `_fmt_signed_percent` L218-228 which divides by 100). Any consumer reading `raw` gets a 100x error.

**Contract gate:** trace `cred_f` production first. If it is already a ratio (and display is the bug), fix display instead. Cite the producing lines in the report.

**Files:**
- Modify: `backend/app/services/executive_service.py`
- Test: existing executive service/API test file (locate via grep), or a focused new test
- Do not modify: schemas, frontend

**Acceptance:**
1. Failing test first proving raw/display disagreement on the credit-concentration signal.
2. Fix makes raw a decimal ratio consistent with display; sibling signals in the same block audited for the same bug (fix only if same pattern, report otherwise).
3. Targeted pytest passes.

## Task 3: Harden shared `_NUMERIC_FIELDS` promote path pct scale

**Tier:** Tier 3 shared backend boundary (evidence-first).

**Problem:** `backend/app/services/explicit_numeric.py::numeric_json` calls `numeric_from_raw` without `raw_scale`, so every `unit="pct"` field promoted via `_NUMERIC_FIELDS` (schemas: pnl_bridge, cashflow_projection, liability_analytics, bond_dashboard, risk_tensor, bond_analytics, pnl_attribution) still rides the legacy `abs(raw)>1` auto heuristic. Sub-1 percent-point values (yields, spreads, small shares) are silently kept as ratio. Same for `pnl_attribution_service.py` L585 `_numeric_json`-style helper.

**Scope control:**
1. Inventory all pct fields flowing through these promote paths; for each, determine the producing raw scale (ratio vs percent-points) from the producing code, citing lines.
2. Extend `_NUMERIC_FIELDS` tuples (or the helper signature) to carry an optional per-field `raw_scale`; default stays `"auto"` so untouched fields keep behavior.
3. Migrate ONLY fields with confirmed evidence; leave ambiguous fields on `"auto"` and list them in the report. If the inventory exceeds ~15 pct fields, migrate the formal finance schemas first (pnl_bridge, cashflow_projection, liability_analytics) and document the rest.

**Files:**
- Modify: `backend/app/services/explicit_numeric.py`, affected schema `_NUMERIC_FIELDS` maps, `backend/app/services/pnl_attribution_service.py` (helper only)
- Test: extend `tests/test_pct_raw_scale_migrated_callers.py` / `tests/test_pct_raw_scale_ratio_callers.py` pattern, plus a unit test on the extended helper
- Do not modify: `common_numeric.py` semantics (only consume existing `raw_scale`)

**Acceptance:**
1. Helper supports per-field raw_scale, default unchanged; unit test for percent/ratio/auto.
2. Migrated fields have producing-code evidence in the report; each migrated schema has at least one regression test with a sub-1 percent-point value.
3. Full pct-related pytest set passes: the two existing raw_scale test files + touched schema/service tests.

**Cancellation note:** Inventory found no live sub-1pp bug on the promote path that required landing shared changes in this round. Concurrent uncommitted patches on `explicit_numeric.py` + cashflow/liability schemas must **not** be staged as Task 3. Replaced by Task 4.

## Task 4: Positions first-screen stale / fallback / no-data closure

**Tier:** Tier 2 page-local display (replaces cancelled Task 3).

**Problem:** Positions primary list did not close first-screen decision states: stale / fallback / unavailable / empty / loading / malformed responses could collapse into false “暂无数据” or crash paths.

**Files:**
- Modify: `frontend/src/features/positions/components/PositionsView.tsx`
- Test: `frontend/src/test/PositionsView.test.tsx`

**Acceptance:**
1. First-screen Alert from active-tab list `result_meta` (stale / fallback / unavailable / error).
2. Main table state machine: loading / error / blocked / empty / ready; no false empty while dates loading.
3. empty only when `total===0 && items.length===0`; `total>0 && items=[] && page>1` resets to page 1.
4. Malformed envelope fail-closed; fallback+stale merged into one warning Alert.
5. Targeted Vitest + typecheck + debt:audit pass.

---

## Execution rules

- Work from `f:\MOSS-V3`
- Minimal diffs; do NOT touch the in-flight macro-freshness/skeleton worktree files
- Do **not** git commit unless controller asks
- One implementer at a time; spec review then quality review per task
- GitNexus/metric-contracts MCP may be unavailable; cite local code/doc evidence instead

## Commit staging checklist (when asked)

**Stage:**
- T1: `PnlBridgePage.tsx` + test + required `PageDataSection.*` + `SkeletonBars.*` (Bridge now imports PageDataSection)
- T2: `executive_service.py` + `test_executive_reserved_surfaces.py` + `tests/test_executive_service_contract.py`
- T4: `PositionsView.tsx` + `PositionsView.test.tsx`
- Optional: this plan doc

**Do not stage:** `DataSection.tsx` Skeleton churn; `explicit_numeric.py`; cashflow/liability schema patches; Formal/ByBusiness PageAsync migrations; other dirty worktree files. Never `git add .`.
