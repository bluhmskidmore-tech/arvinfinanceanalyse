# Livermore Real Theme Data Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the first-pass name proxy with optional real concept-board membership and intraday movement inputs, while keeping the radar observation-only and fail-closed when those real inputs are absent.

**Architecture:** Extend the Choice stock catalog with optional input families, add DuckDB tables for concept membership and intraday movement events, and let the existing stock materializer persist those optional rows when confirmed catalog entries exist. The Livermore theme radar will prefer real concept groups and movement evidence; only when no concept rows are landed will it fall back to the prior proxy logic.

**Tech Stack:** Python, DuckDB schema registry, configurable Choice/EmQuant request catalog, Livermore backend service, TypeScript contracts/models, pytest, Vitest.

---

### Task 1: Optional Catalog Families

**Files:**
- Modify: `backend/app/repositories/choice_stock_adapter.py`
- Modify: `tests/test_choice_stock_adapter.py`

**Steps:**
1. Write a failing test that a confirmed optional `concept_membership` / `intraday_movement` entry is accepted without becoming a required readiness gate.
2. Include optional confirmed entries in `load_choice_stock_request_plan`.
3. Keep `CHOICE_STOCK_REQUIRED_INPUT_FAMILIES` unchanged.

### Task 2: Materialize Real Theme Inputs

**Files:**
- Modify: `backend/app/schema_registry/duckdb/21_choice_stock.sql`
- Modify: `backend/app/tasks/choice_stock_materialize.py`
- Modify: `tests/test_choice_stock_materialize.py`

**Steps:**
1. Write a failing test with fake Choice `css` and `ctr` responses.
2. Add `choice_stock_concept_membership`.
3. Add `choice_stock_intraday_movement_event`.
4. Normalize flexible vendor column names into stable columns.
5. Delete/reinsert optional rows idempotently with the stock materialization run.
6. Keep missing optional inputs out of base stock coverage.

### Task 3: Theme Radar Uses Real Inputs First

**Files:**
- Modify: `backend/app/core_finance/livermore_theme_breakout.py`
- Modify: `backend/app/services/market_data_livermore_service.py`
- Modify: `tests/test_livermore_theme_breakout.py`
- Modify: `tests/test_livermore_theme_breakout_service.py`

**Steps:**
1. Write failing tests showing a real concept group is emitted with `is_proxy = false`.
2. Add optional concept and movement fields to snapshots.
3. Load concept membership and movement event aggregates when tables exist.
4. Only fall back to proxy when no real concept rows are landed.

### Task 4: Frontend Boundary Copy

**Files:**
- Modify: `frontend/src/api/contracts.ts`
- Modify: `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts`
- Modify: `frontend/src/test/StockAnalysisPageModel.test.ts`

**Steps:**
1. Add movement evidence fields to the contract.
2. Show whether the card came from real concept/movement data or proxy.
3. Keep the section free of buy/sell/order wording.

### Task 5: Verify

Run:
- `.venv\Scripts\python.exe -m pytest tests/test_choice_stock_adapter.py tests/test_choice_stock_materialize.py tests/test_livermore_theme_breakout.py tests/test_livermore_theme_breakout_service.py tests/test_market_data_livermore_api.py -q`
- `npm run test -- StockAnalysisPageModel.test.ts StockAnalysisPage.test.tsx livermoreStrategyModel.test.ts`
- `npm run typecheck`
- `npm run debt:audit`
