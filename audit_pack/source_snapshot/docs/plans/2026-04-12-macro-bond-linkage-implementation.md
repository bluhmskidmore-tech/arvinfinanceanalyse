# Macro Bond Linkage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a governed macro-bond linkage analysis slice that computes macro/yield correlations, macro environment scoring, and portfolio impact through `core_finance -> service -> api`.

**Architecture:** Keep formal-style calculations isolated in `backend/app/core_finance/macro_bond_linkage.py`, let the service read DuckDB and risk inputs, assemble analytical `result_meta`, and expose one thin FastAPI route. Use pure-Python correlation logic and fail-soft warnings when macro data is insufficient.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, DuckDB, pytest

---

### Task 1: Write the failing contract tests

**Files:**
- Create: `tests/test_macro_bond_linkage.py`
- Reference: `tests/test_macro_query_contract_smoke.py`
- Reference: `tests/test_risk_tensor_api.py`

**Step 1: Write the failing test**

Add tests for:
- pure-Python Pearson correlation
- lead/lag detection
- rising-rate environment score
- falling-rate environment score
- portfolio impact estimation
- API envelope + warning behavior

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro_bond_linkage.py -q`

Expected: FAIL because the new core/service/api modules are missing.

### Task 2: Add the core finance calculation module

**Files:**
- Create: `backend/app/core_finance/macro_bond_linkage.py`
- Reference: `backend/app/core_finance/risk_tensor.py`

**Step 1: Write minimal implementation**

Implement:
- indicator group constants
- `MacroBondCorrelation`
- `MacroEnvironmentScore`
- pure-Python Pearson correlation helper
- rolling correlation windows
- best lead/lag search in `[-30, 30]`
- environment score logic
- portfolio impact estimation

**Step 2: Run test to verify progress**

Run: `python -m pytest tests/test_macro_bond_linkage.py -q`

Expected: core-only tests move closer to green while service/API tests still fail.

### Task 3: Add schema, service orchestration, and route registration

**Files:**
- Create: `backend/app/schemas/macro_bond_linkage.py`
- Create: `backend/app/services/macro_bond_linkage_service.py`
- Create: `backend/app/api/routes/macro_bond_linkage.py`
- Modify: `backend/app/api/__init__.py`

**Step 1: Write minimal implementation**

Implement:
- response payload schema
- DuckDB reads for `fact_choice_macro_daily` and governed curve tables
- portfolio DV01/CS01 lookup from `fact_formal_risk_tensor_daily` with bond-analytics fallback
- analytical `result_meta` envelope
- `/api/macro-bond-linkage/analysis`

**Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_macro_bond_linkage.py -q`

Expected: PASS

### Task 4: Run focused regression checks

**Files:**
- Reference: `backend/app/api/__init__.py`
- Reference: `backend/app/services/formal_result_runtime.py`

**Step 1: Run verification**

Run: `python -m pytest tests/test_macro_bond_linkage.py tests/test_macro_query_contract_smoke.py tests/test_risk_tensor_api.py -q`

Expected: PASS

**Step 2: Review risks**

Confirm:
- no finance formulas in API
- result is analytical and still carries `result_meta`
- insufficient macro history returns warnings instead of silent numeric fabrication
