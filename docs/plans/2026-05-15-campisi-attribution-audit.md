# Campisi Attribution Audit Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Independently audit `/pnl-attribution` Campisi attribution calculations across four-effect, six-effect, maturity-bucket, legacy fallback, and frontend display paths.

**Architecture:** Treat Campisi as a separate calculation chain, not as part of the advanced-summary percentage fix. Audit from source rows and market curves into pure finance functions, service envelopes, API contracts, frontend panels, and browser output. Prefer evidence and golden samples over formula assumptions; surface ambiguity rather than guessing metric definitions.

**Tech Stack:** Python/FastAPI, DuckDB read models, Pydantic `Numeric`, React/Vitest, pytest, Playwright, project MCP evidence servers when available.

---

## Scope

Audit only the Campisi workflow displayed on `http://localhost:5888/pnl-attribution`:

- Current Campisi endpoints:
  - `/api/pnl-attribution/campisi/four-effects`
  - `/api/pnl-attribution/campisi/enhanced`
  - `/api/pnl-attribution/campisi/maturity-buckets`
- Legacy page fallback:
  - `/api/pnl-attribution/advanced/campisi`
- Frontend render path:
  - `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
  - `frontend/src/features/pnl-attribution/components/CampisiAttributionPanel.tsx`
  - `frontend/src/features/pnl-attribution/components/CampisiEnhancedPanel.tsx`
  - `frontend/src/features/pnl-attribution/components/CampisiMaturityBucketPanel.tsx`

Do not touch database schema, materialization jobs, auth, global SDK wrappers, unrelated dashboard/type debt, or non-Campisi attribution formulas.

## Audit Questions

1. Does every Campisi result close internally?
   - Four-effect: `total_return = income_return + treasury_effect + spread_effect + selection_effect`
   - Six-effect: `total_return = income_return + treasury_effect + spread_effect + convexity_effect + cross_effect + reinvestment_effect + selection_effect`
   - Maturity buckets: bucket sums equal the same four-effect totals.
2. Are all units consistent?
   - Coupon/YTM normalized to decimal annual rates before income/duration math.
   - Treasury yields treated as percent points at curve input, then converted to decimal delta by `/100`.
   - Credit spreads treated as bp, then converted to decimal delta by `/10000`.
   - Frontend percentages use governed `Numeric.display` or explicitly documented percent-point values.
3. Is accounting basis handled correctly?
   - AC holdings only contribute income; treasury, spread, and selection are zero.
4. Is total return basis correct?
   - Full-price basis when both accrued-interest sides exist.
   - Clean-price plus estimated income fallback only when accrued interest is missing, with warning.
5. Are source lineage, stale/fallback dates, and formal closure surfaced?
   - Anchor start/end dates are explicit.
   - Curve/spread coverage gaps are warnings, not silently treated as correct.
   - Formal PnL residual is shown and not hidden.

## Task 1: Evidence And Contract Inventory

**Files to inspect only:**
- `backend/app/core_finance/campisi.py`
- `backend/app/core_finance/bond_four_effects.py`
- `backend/app/services/campisi_attribution_service.py`
- `backend/app/services/pnl_attribution_service.py`
- `backend/app/api/routes/campisi_attribution.py`
- `backend/app/api/routes/pnl_attribution.py`
- `frontend/src/api/pnlClient.ts`
- `frontend/src/api/contracts.ts`
- `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
- Campisi panel files listed in Scope

**Steps:**
1. Query project MCP evidence servers if available:
   - `moss-metric-contracts`: Campisi metric definitions, units, golden samples.
   - `moss-lineage-evidence`: rule/cache/source lineage and fallback/stale status.
   - `moss-data-catalog`: available DuckDB tables, columns, and dates.
   - `gitnexus`: call paths and shared-symbol impact.
2. If any MCP server is unavailable, record the server name, local fallback evidence, and residual risk in the audit notes.
3. Map exact call chain:
   - API route → service envelope → `merge_positions` → market curve loading → `campisi_attribution` / `campisi_enhanced` / `maturity_bucket_attribution` → schema/contract → React panel.
4. Write an audit note with field-level units for every displayed Campisi metric.

**Exit criteria:**
- A one-page evidence map exists in the work notes.
- Every displayed Campisi number has a source field, unit, and formula owner.

## Task 2: Pure Formula Golden Tests

**Files:**
- Modify or create tests near: `tests/test_attribution_daily.py`, `backend/tests/services/test_pnl_attribution_campisi.py`, or a new focused file such as `tests/test_campisi_formula_golden.py`.
- Inspect: `backend/app/core_finance/bond_four_effects.py`
- Inspect: `backend/app/core_finance/campisi.py`

**Steps:**
1. Create a one-bond government/FVTPL fixture with:
   - known `market_value_start`, `market_value_end`, `face_value_start`, `coupon_rate_start`, `yield_to_maturity_start`, `maturity_date_start`, accrued interest start/end, treasury start/end curves, no spread.
2. Hand-compute expected:
   - `income_return = coupon_rate_decimal * face_value_start * num_days / 365`
   - `benchmark_yield_change = interpolated_treasury_end - interpolated_treasury_start`
   - `treasury_effect = -modified_duration * benchmark_yield_change_decimal * market_value_start`
   - `spread_effect = 0`
   - `total_return = (market_value_end + accrued_interest_end) - (market_value_start + accrued_interest_start)`
   - `selection_effect = total_return - income_return - treasury_effect - spread_effect`
3. Create a one-bond credit/FVTPL fixture with known credit spread movement and verify spread-effect sign and unit.
4. Create a one-bond AC fixture and verify:
   - `treasury_effect = 0`
   - `spread_effect = 0`
   - `selection_effect = 0`
   - `total_return = income_return`
5. Create a missing-accrued-interest fixture and verify clean-price fallback plus warning.
6. Run each test first against current code, record pass/fail and any discrepancy.

**Exit criteria:**
- Golden tests prove formula behavior for government, credit, AC, and missing-accrued cases.
- Any failure is classified as formula bug, unit bug, or expected-but-undocumented behavior.

## Task 3: Service Input Lineage And Aggregation Audit

**Files:**
- `backend/app/services/campisi_attribution_service.py`
- `backend/app/services/pnl_attribution_service.py`
- `backend/tests/services/test_pnl_attribution_campisi.py`

**Steps:**
1. Add service-level tests with monkeypatched bond rows and curves for:
   - start/end date anchoring on or before requested dates.
   - `merge_positions` aggregation by business position key.
   - duplicate instrument code warning.
   - missing pricing/classification warning.
   - credit spread coverage warning.
2. Verify totals equal summed leaves:
   - `totals` equals sum of `by_bond`.
   - `by_asset_class` equals grouped `by_bond`.
   - maturity buckets equal four-effect totals.
3. Verify `formal_closure`:
   - closed when formal PnL matches Campisi total.
   - warning/residual when it does not.
4. Compare legacy `/advanced/campisi` output against current `/campisi/four-effects` for the same golden fixtures.

**Exit criteria:**
- Service envelopes expose correct metadata, warnings, and closure.
- No aggregation path silently drops or double-counts positions.

## Task 4: API Contract And Live Data Probe

**Commands:**
- `python -m pytest backend/tests/services/test_pnl_attribution_campisi.py -q`
- `python -m pytest tests/test_pnl_attribution_service_explicit_numeric.py -q`
- `python -m pytest tests/test_attribution_daily.py -q`

**Live probe script:**
```powershell
@'
import json, urllib.request
base = "http://127.0.0.1:7888"
paths = [
  "/api/pnl-attribution/campisi/four-effects?end_date=2026-04-30&lookback_days=30",
  "/api/pnl-attribution/campisi/enhanced?end_date=2026-04-30&lookback_days=30",
  "/api/pnl-attribution/campisi/maturity-buckets?end_date=2026-04-30&lookback_days=30",
  "/api/pnl-attribution/advanced/campisi?end_date=2026-04-30&lookback_days=30",
]
for path in paths:
    with urllib.request.urlopen(base + path, timeout=30) as response:
        envelope = json.load(response)
    print(path)
    print(json.dumps({
        "meta": envelope.get("result_meta"),
        "warnings": (envelope.get("result") or {}).get("warnings"),
        "formal_closure": (envelope.get("result") or {}).get("formal_closure"),
    }, ensure_ascii=False, indent=2))
'@ | python -
```

**Steps:**
1. Confirm every `Numeric` field uses the contract unit expected by `frontend/src/api/contracts.ts`.
2. Confirm API-level closure from JSON without relying on UI.
3. Record live `result_meta`, warning state, and residual state for the report date.

**Exit criteria:**
- Live API output either closes and has no material warnings, or clearly surfaces residual/warnings.
- No percentage/value field is ambiguous between raw ratio and percent points.

## Task 5: Frontend Display Audit

**Files:**
- `frontend/src/features/pnl-attribution/components/CampisiAttributionPanel.tsx`
- `frontend/src/features/pnl-attribution/components/CampisiEnhancedPanel.tsx`
- `frontend/src/features/pnl-attribution/components/CampisiMaturityBucketPanel.tsx`
- relevant frontend tests under `frontend/src/test/`

**Steps:**
1. Add/adjust frontend tests so panels render governed values from representative current endpoint payloads.
2. Verify the four-effect panel does not recompute a displayed percentage differently from the backend contract unless it is explicitly a contribution share.
3. Verify formal closure warnings show when `formal_closure.status !== "closed"`.
4. Verify warnings and empty states are visible.
5. Use Playwright on `/pnl-attribution`, switch to `高级归因 + Campisi`, and compare visible values to API JSON.

**Commands:**
- `npm run test -- <focused Campisi panel tests>`
- `npm run debt:audit`

**Exit criteria:**
- UI values match API JSON or a documented frontend-only transform.
- Warnings/residuals are visible on the page.

## Task 6: Audit Report And Fix Decision

**Deliverable:**
- A concise audit report with:
  - formula verdict by component: four-effect, six-effect, maturity bucket, legacy fallback, frontend display.
  - exact root causes for any mismatch.
  - evidence paths and commands run.
  - residual risks, especially unavailable MCP evidence or missing golden samples.
  - recommended fixes split into "must fix now" and "can defer".

**If bugs are found:**
1. Write the smallest failing test first.
2. Fix only the failing Campisi path.
3. Re-run the narrow test, then the broader commands listed above.
4. Do not commit unless explicitly requested.

## Acceptance Criteria

- Four-effect, six-effect, and maturity-bucket internal closure verified to tolerance.
- Unit conversions verified for coupon/YTM, treasury, credit spread, percentage displays, and yuan/yi display.
- AC treatment verified.
- Full-price vs clean-price fallback verified and warnings surfaced.
- Current and legacy Campisi endpoints compared for page behavior.
- Frontend page values match API values for the report date.
- `npm run debt:audit` passes after any frontend change.
- Any unrelated existing lint/build failures are reported separately and not fixed as part of this audit.
