# Livermore Theme Breakout Radar Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an observation-only theme breakout radar so the stock workflow can surface strong sub-theme clusters even when their parent Shenwan level-1 sector is outside the top-3 Livermore candidate gate.

**Architecture:** Keep the current Livermore market gate, sector rank, stock candidate, and risk-exit outputs unchanged. Add a separate `theme_breakout` payload built from existing Choice daily stock observations, level-1 sector membership, and limit-up quality rows. The payload is explicitly proxy-based because no true concept or level-2 industry feed is currently available in the landed tables.

**Tech Stack:** Python service/core finance module, DuckDB read-only queries, TypeScript API contracts, React stock analysis page, pytest, Vitest.

---

### Task 1: Backend Pure Function Test

**Files:**
- Create: `tests/test_livermore_theme_breakout.py`
- Create later: `backend/app/core_finance/livermore_theme_breakout.py`

**Step 1: Write the failing test**

Add a test that passes several `ThemeBreakoutSnapshot` rows where:
- Parent sector `801080` / `Electronic` has `sector_rank = 9`.
- Three semiconductor-like stock names have strong daily performance.
- At least two are limit-up or near limit-up.
- The resulting payload contains one theme item with `theme_key = "semiconductor_proxy"`.
- The payload says `is_proxy = True` and does not contain buy/sell/trading wording.

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_livermore_theme_breakout.py -q`

Expected: fail because the module does not exist yet.

### Task 2: Backend Core Implementation

**Files:**
- Create: `backend/app/core_finance/livermore_theme_breakout.py`

**Step 1: Implement the minimal pure function**

Create:
- `FORMULA_VERSION = "rv_livermore_theme_breakout_proxy_v1"`
- `ThemeBreakoutSnapshot`
- `compute_theme_breakout(as_of_date, snapshots)`

Behavior:
- Group stock rows into a small proxy taxonomy, starting with `semiconductor_proxy`.
- Use existing row-level evidence only: percent change, turnover, amplitude, close position in the day range, sector rank, limit-up flag.
- Allow themes from parent sector ranks outside top 3 when the cluster itself is strong.
- Return observation-only text and no trading instructions.

**Step 2: Run the pure test**

Run: `.venv\Scripts\python.exe -m pytest tests/test_livermore_theme_breakout.py -q`

Expected: pass.

### Task 3: Service Integration

**Files:**
- Modify: `backend/app/services/market_data_livermore_service.py`

**Step 1: Add read-only input loader**

Load theme snapshots from:
- `choice_stock_daily_observation`
- `choice_stock_sector_membership`
- `choice_stock_universe`
- Optional `choice_stock_limit_quality`

**Step 2: Add payload to Livermore response**

Include:
- `payload["theme_breakout"]`
- `supported_outputs += ["theme_breakout"]`
- A warning diagnostic that the branch is proxy-based and not intraday/concept-authoritative.

**Step 3: Run targeted backend checks**

Run:
- `.venv\Scripts\python.exe -m pytest tests/test_livermore_theme_breakout.py tests/test_livermore_stock_candidates.py tests/test_market_data_livermore_api.py -q`

Expected: pass.

### Task 4: Frontend Contract And Model

**Files:**
- Modify: `frontend/src/api/contracts.ts`
- Modify: `frontend/src/features/market-data/lib/livermoreStrategyModel.ts`
- Modify: `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts`
- Modify: `frontend/src/test/StockAnalysisPageModel.test.ts`

**Step 1: Add contract types**

Add `theme_breakout` to `LivermoreOutputKey` and define theme/stock item payload types.

**Step 2: Add stock page model builder**

Expose `buildThemeBreakoutCards(payload)` and keep copy observation-only.

**Step 3: Run model test**

Run: `npm run test -- StockAnalysisPageModel.test.ts`

Expected: pass.

### Task 5: Frontend Page Rendering

**Files:**
- Modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Modify: `frontend/src/test/StockAnalysisPage.test.tsx`

**Step 1: Render a theme radar section**

Add a compact section near the sector/candidate review area with `data-testid="stock-analysis-theme-breakout"`.

**Step 2: Run page and debt checks**

Run:
- `npm run test -- StockAnalysisPage.test.tsx`
- `npm run typecheck`
- `npm run debt:audit`

Expected: pass, or report any pre-existing unrelated failures separately.
