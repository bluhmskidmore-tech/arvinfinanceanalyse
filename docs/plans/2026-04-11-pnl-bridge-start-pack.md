# PnL Bridge Start Pack Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a formal `pnl/bridge` start pack that builds bridge rows from formal PnL facts plus current/prior balance rows, and returns a governed `result_meta` envelope.

**Architecture:** Keep all bridge math in `backend/app/core_finance/pnl_bridge.py`. Let `services/` orchestrate repository reads, prior-date selection, warnings, summary aggregation, and `result_meta`; let `api/` only validate/call service/return response.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, DuckDB repositories, existing formal result envelope helpers.

---

### Task 1: Lock Core Bridge Behavior

**Files:**
- Create: `tests/test_pnl_bridge_core.py`
- Read: `backend/app/core_finance/pnl.py`

**Step 1: Write the failing tests**

- `test_bridge_carry_equals_514`
- `test_bridge_residual_calculation`
- `test_bridge_quality_flag_thresholds`
- `test_bridge_missing_prior_balance_graceful`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pnl_bridge_core.py -q`

Expected: fail because `backend.app.core_finance.pnl_bridge` does not exist yet.

### Task 2: Implement Core Builder

**Files:**
- Create: `backend/app/core_finance/pnl_bridge.py`
- Modify: `backend/app/core_finance/__init__.py`

**Step 1: Add `PnlBridgeRow` dataclass and builder**

- Map `carry` to `interest_income_514`
- Map `realized_trading` to `capital_gain_517`
- Map `unrealized_fv` to `fair_value_change_516`
- Keep `roll_down / treasury_curve / credit_spread / fx_translation = 0`
- Compute dirty market values from `market_value + accrued_interest`
- Compute explained / actual / residual / residual_ratio / quality_flag

**Step 2: Re-run core tests**

Run: `pytest tests/test_pnl_bridge_core.py -q`

Expected: core tests pass.

### Task 3: Add Schema, Service, Route

**Files:**
- Create: `backend/app/schemas/pnl_bridge.py`
- Create: `backend/app/services/pnl_bridge_service.py`
- Modify: `backend/app/api/routes/pnl.py`

**Step 1: Add JSON schema**

- Row schema with Decimal serialized as string
- Payload schema with `report_date`, `rows`, `summary`, `warnings`

**Step 2: Add service orchestration**

- Read PnL rows from `PnlRepository`
- Read current/prior balance rows from `BalanceAnalysisRepository`
- Build rows, warnings, summary
- Return formal `result_meta` envelope

**Step 3: Add API endpoint**

- `GET /api/pnl/bridge?report_date=...`

### Task 4: Verify Regressions

**Files:**
- Read: `tests/test_pnl_api_contract.py`

**Step 1: Run targeted verification**

Run:
- `pytest tests/test_pnl_bridge_core.py -q`
- `pytest tests/test_pnl_api_contract.py -q`

**Step 2: Check risks**

- Balance lookup key shape vs PnL fact grain
- Prior-period selection behavior
- Bridge warnings/result_meta lineage consistency

### Decision Note (2026-04-12)

- `fact_pnl_bridge_daily` remains deferred in this round.
- Rationale:
  - The start-pack still has four Phase 3 factors fixed at `0`.
  - The bridge currently serves a single governed read path.
  - Materializing now would add write-path, cache, governance, and regression burden without improving calculation truth.
- Revisit materialization after at least one real Phase 3 factor (`roll_down` or `treasury_curve`) is implemented or when a second stable consumer appears.
