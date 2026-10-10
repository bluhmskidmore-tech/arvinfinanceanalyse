# Macro Bond Linkage Statistical Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden the macro-bond linkage analysis with dual-track frequency alignment, z-score normalization, winsorization, and lead-lag confidence metadata while keeping the top-level response contract backward compatible and leaving `environment_score` unchanged.

**Architecture:** Keep all statistical logic in `backend/app/core_finance/macro_bond_linkage.py`, add only additive analytical contract fields in schema/service, and preserve the existing top-level `top_correlations` by mapping it to the `conservative` method variant. Do not add frontend consumers, do not change formal paths, and do not refactor `environment_score` in this round.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, DuckDB, pytest

---

### Task 1: Lock the new contract with failing tests first

**Files:**
- Modify: `F:\MOSS-V3\tests\test_macro_bond_linkage.py`
- Reference: `F:\MOSS-V3\backend\app\schemas\macro_bond_linkage.py`
- Reference: `F:\MOSS-V3\backend\app\services\macro_bond_linkage_service.py`

**Step 1: Write the failing test**

Add tests for:
- `method_variants.conservative` and `method_variants.market_timing` both exist
- top-level `top_correlations` exactly mirrors `method_variants.conservative.top_correlations`
- correlation items carry additive metadata:
  - `alignment_mode`
  - `sample_size`
  - `winsorized`
  - `zscore_applied`
  - `lead_lag_confidence`
  - `effective_observation_span_days`
- `environment_score` remains present and backward compatible
- low-frequency macro vs daily yield produces different sample shapes across the two alignment modes

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro_bond_linkage.py -q`

Expected: FAIL because the new `method_variants` structure and metadata fields do not exist yet.

### Task 2: Add dual-track analytical primitives in `core_finance`

**Files:**
- Modify: `F:\MOSS-V3\backend\app\core_finance\macro_bond_linkage.py`
- Test: `F:\MOSS-V3\tests\test_macro_bond_linkage.py`

**Step 1: Write the failing test**

Add narrow tests for pure functions that prove:
- `conservative` alignment only samples at macro observation points / lowest common frequency
- `market_timing` alignment forward-fills between macro observations to trading dates
- z-score normalization preserves sign and makes scale differences irrelevant
- winsorization clips extreme tails without collapsing all variance
- lead-lag confidence decreases when the best lag is close to the runner-up or sample size is weak

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro_bond_linkage.py -k "alignment or zscore or winsor or confidence" -q`

Expected: FAIL because the helper functions do not exist yet.

**Step 3: Write minimal implementation**

Implement the smallest private helper set in `core_finance`:
- frequency classification / normalization for series
- `conservative` alignment
- `market_timing` alignment
- rolling or window-scoped z-score normalization
- percentile-based winsorization
- confidence calculation from:
  - best correlation magnitude
  - gap to runner-up lag
  - effective sample size
- additive method-variant payload builder while keeping `MacroBondCorrelation` backward compatible or minimally extended

Do **not** change `compute_macro_environment_score()` semantics in this round.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_macro_bond_linkage.py -k "alignment or zscore or winsor or confidence" -q`

Expected: PASS

### Task 3: Extend schema and service contract additively

**Files:**
- Modify: `F:\MOSS-V3\backend\app\schemas\macro_bond_linkage.py`
- Modify: `F:\MOSS-V3\backend\app\services\macro_bond_linkage_service.py`
- Test: `F:\MOSS-V3\tests\test_macro_bond_linkage.py`

**Step 1: Write the failing test**

Add service-level assertions for:
- `result.method_variants.conservative.top_correlations`
- `result.method_variants.market_timing.top_correlations`
- `result.method_variants.*.method_meta`
- top-level `top_correlations` equals the conservative variant
- top-level `report_date`, `environment_score`, `portfolio_impact`, `warnings`, and `computed_at` remain compatible

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro_bond_linkage.py -k "method_variants or conservative" -q`

Expected: FAIL because schema and service do not expose the new fields yet.

**Step 3: Write minimal implementation**

In schema:
- Add typed models for:
  - method-level metadata
  - method-level correlation lists
  - additive `method_variants`

In service:
- Keep `top_correlations` as the default conservative result
- Add `method_variants` with:
  - `conservative`
  - `market_timing`
- Preserve existing top-level fields
- Surface method warnings and metadata without changing top-level envelope shape

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_macro_bond_linkage.py -q`

Expected: PASS

### Task 4: Verify non-regression for current analytical consumer contract

**Files:**
- Reference: `F:\MOSS-V3\backend\app\services\macro_bond_linkage_service.py`
- Reference: `F:\MOSS-V3\backend\app\schemas\macro_bond_linkage.py`

**Step 1: Run regression verification**

Run: `python -m pytest tests/test_macro_bond_linkage.py tests/test_macro_query_contract_smoke.py tests/test_no_finance_logic_in_api.py -q`

Expected: PASS

**Step 2: Run static checks**

Run: `python -m ruff check backend/app/core_finance/macro_bond_linkage.py backend/app/schemas/macro_bond_linkage.py backend/app/services/macro_bond_linkage_service.py tests/test_macro_bond_linkage.py`

Expected: PASS

### Task 5: Record method assumptions and explicit non-goals in code comments / docs

**Files:**
- Modify: `F:\MOSS-V3\backend\app\core_finance\macro_bond_linkage.py`
- Optional supplement: `F:\MOSS-V3\docs\plans\2026-04-13-macro-bond-linkage-statistical-hardening-plan.md`

**Step 1: Add bounded explanatory comments**

Add only short comments where needed to clarify:
- why `conservative` is the default top-level track
- why `environment_score` is intentionally unchanged
- what `lead_lag_confidence` measures at a high level

**Step 2: Re-run the full verification**

Run:
- `python -m pytest tests/test_macro_bond_linkage.py tests/test_macro_query_contract_smoke.py tests/test_no_finance_logic_in_api.py -q`
- `python -m ruff check backend/app/core_finance/macro_bond_linkage.py backend/app/schemas/macro_bond_linkage.py backend/app/services/macro_bond_linkage_service.py tests/test_macro_bond_linkage.py`

Expected: PASS

---

## Cursor Split

### Cursor Task 1: Schema Contract Pass

**Files:**
- Modify: `F:\MOSS-V3\backend\app\schemas\macro_bond_linkage.py`
- Reference: `F:\MOSS-V3\tests\test_macro_bond_linkage.py`

**Step 1: Write the failing test**

Add schema-focused tests in `tests/test_macro_bond_linkage.py` for additive `method_variants` shape.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro_bond_linkage.py -k "schema or method_variants" -q`

Expected: FAIL

**Step 3: Write minimal implementation**

Add typed schema models only. Do not modify `core_finance`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_macro_bond_linkage.py -k "schema or method_variants" -q`

Expected: PASS

### Cursor Task 2: Service Envelope Pass

**Files:**
- Modify: `F:\MOSS-V3\backend\app\services\macro_bond_linkage_service.py`
- Reference: `F:\MOSS-V3\backend\app\schemas\macro_bond_linkage.py`
- Test: `F:\MOSS-V3\tests\test_macro_bond_linkage.py`

**Step 1: Write the failing test**

Add service-envelope assertions for conservative top-level mirroring and additive `method_variants`.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro_bond_linkage.py -k "service and conservative" -q`

Expected: FAIL

**Step 3: Write minimal implementation**

Wire the additive response fields only. Do not redesign algorithms.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_macro_bond_linkage.py -k "service and conservative" -q`

Expected: PASS

---

## Hard Task For Me

I should own the algorithmic work in `backend/app/core_finance/macro_bond_linkage.py`:
- alignment strategies
- z-score normalization
- winsorization
- lead-lag confidence scoring
- regression safety around sample size and output stability

That is the highest-risk part and should not be delegated as the “simple” lane.

## Verification Checklist

- [ ] `method_variants` exists and is additive
- [ ] top-level `top_correlations` mirrors `conservative`
- [ ] `environment_score` remains backward compatible
- [ ] dual-track alignment behavior is test-locked
- [ ] z-score and winsorization behavior is test-locked
- [ ] lead-lag confidence is present and test-locked
- [ ] full targeted pytest suite passes
- [ ] ruff passes on touched backend files

Plan complete and saved to `docs/plans/2026-04-13-macro-bond-linkage-statistical-hardening-plan.md`.

Two execution options:

1. Subagent-Driven (this session) - I dispatch bounded tasks and review/integrate them here.
2. Parallel Session (separate) - Execute this plan in a dedicated follow-up session.
