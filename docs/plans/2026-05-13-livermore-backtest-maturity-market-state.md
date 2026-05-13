# Livermore Backtest Maturity And Market State Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Livermore candidate replay explain poor weekly picks by separating per-horizon maturity from full-row completion and by splitting strategy performance by market gate state.

**Architecture:** Keep the existing candidate-history table and API path. Store market state inside each row's `signal_evidence_json` during materialization, then compute summary groupings from normalized rows without schema changes.

**Tech Stack:** Python DuckDB services/tasks, pytest, TypeScript React, Vitest, existing Stock Analysis and Market Data pages.

---

### Task 1: Backend Horizon-Usable Stats

**Files:**
- Modify: `backend/app/services/livermore_candidate_history_service.py`
- Test: `tests/test_market_data_livermore_candidate_history.py`

**Intent:**
Current `decision_usable_stats` excludes rows unless `data_status == "complete"`. Because `complete` means T+1, T+5, and T+20 are all present, early windows hide already-mature T+1/T+5 results. Add a horizon-usable stats block that includes rows on replay-covered dates and computes each horizon from its own available returns.

**Steps:**
1. Add a failing service test with rows where `return_1d` and `return_5d` are present but `return_20d` is null and `data_status` is `pending`.
2. Assert the new summary contains horizon-level counts and win rates for T+1/T+5 while T+20 remains missing.
3. Implement minimal helper that filters by included replay dates but does not require `data_status == "complete"` for every horizon.
4. Preserve the existing `decision_usable_stats` fields for compatibility.
5. Run `python -m pytest -q tests/test_market_data_livermore_candidate_history.py`.

**Acceptance:**
- Existing consumers of `decision_usable_stats` still work.
- New `horizon_usable_stats` reports mature T+1/T+5 even when T+20 is pending.

### Task 2: Backend Market-State Grouping

**Files:**
- Modify: `backend/app/tasks/livermore_candidate_history_materialize.py`
- Modify: `backend/app/services/livermore_candidate_history_service.py`
- Test: `tests/test_market_data_livermore_candidate_history.py`

**Intent:**
We need to know whether a strategy fails because the market is WARM/HOT/OVERHEAT. Avoid schema churn by writing `market_state` into `signal_evidence_json`, then grouping summary stats by market state and signal kind.

**Steps:**
1. Add a failing materialization/service test that creates two rows with different `market_gate.state` values.
2. Assert normalized summary exposes `by_market_state_signal_kind_horizon_stats`.
3. Add `market_state` to each signal row's `signal_evidence`.
4. Parse `signal_evidence_json` defensively in the service; use `"unknown"` when absent.
5. Run `python -m pytest -q tests/test_market_data_livermore_candidate_history.py`.

**Acceptance:**
- No table schema change.
- Existing historical rows without market state remain grouped as `unknown`.
- New rows can answer “趋势突破在 OVERHEAT 下 T+1/T+5 表现如何”.

### Task 3: Frontend Strategy Replay Panel

**Files:**
- Modify: `frontend/src/api/contracts.ts`
- Modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Test: `frontend/src/test/StockAnalysisPage.test.tsx`

**Intent:**
Make the Stock Analysis page show the corrected horizon-usable stats first, then market-state breakdown below it.

**Steps:**
1. Extend contracts with optional `horizon_usable_stats` and `by_market_state_signal_kind_horizon_stats`.
2. Update the existing “策略回溯表现” table to prefer horizon-usable stats.
3. Add a compact market-state breakdown table with rows like `OVERHEAT / 趋势突破`.
4. Update Vitest to assert pending T+20 does not hide mature T+1/T+5.
5. Run `npm test -- StockAnalysisPage.test.tsx` and `npm run typecheck`.

**Acceptance:**
- Page communicates T+1/T+5 maturity separately from T+20.
- User can compare WARM/HOT/OVERHEAT by strategy.

### Task 4: Integration Verification

**Files:**
- No production edits expected.
- Test: related backend and frontend test suites.

**Steps:**
1. Run backend focused tests:
   `python -m pytest -q tests/test_choice_stock_materialize.py tests/test_market_data_livermore_candidate_history.py tests/test_livermore_signal_confluence.py tests/test_livermore_theme_breakout_service.py tests/test_livermore_theme_breakout.py tests/test_market_data_livermore_api.py`
2. Run frontend focused tests:
   `npm test -- EchartsBoundary.test.ts MarketDataPage.test.tsx StockAnalysisPage.test.tsx StockDetailDrawer.test.tsx`
3. Run `npm run typecheck`.
4. Run `npm run debt:audit`.
5. Open `/stock-analysis` in the browser and confirm “策略回溯表现” shows horizon-usable and market-state rows.

**Acceptance:**
- Tests pass.
- No frontend debt growth.
- Browser renders the updated panel without crashing.
