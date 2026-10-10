# M10 Leading Indicator Common-Month Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make M10 calculate its observation-only LEI from the latest strict six-component common month, using a governed 12-month primary history and a 24-month shadow comparison.

**Architecture:** Preserve the shared wide-row forward fill for other macro capabilities, but attach source-date provenance and let M10 rebuild true monthly observations from that provenance. M10 selects the latest month available to all six components, rejects partial-month scoring, uses the last real in-month daily observation for market legs, and exposes alignment, coverage, unit-status, and shadow-window evidence. The API evidence layer must pair every derived value with its actual source date and derivation rather than an unrelated alias snapshot.

**Tech Stack:** Python, FastAPI route helpers, DuckDB read-only loaders, Decimal calculations, pytest, Ruff.

**Approved owner decisions (2026-07-20):**

- Primary alignment: strict 6/6 latest common computable economic month.
- Daily-to-month mapping: last real in-month observation; no future row and no cross-month carry.
- Primary history: 12 complete calendar months before `as_of_month`; missing months remain missing.
- Challenger: 24-month shadow result; no 36-month output.
- No common month: `unavailable`, with no LEI, economic state, score, or primary metric.
- Units with unresolved vendor metadata may remain provisional only for observation output, with explicit warnings; formal use remains forbidden.
- Do not modify weights, score formulas, thresholds, database schema, refresh tasks, or frontend calculations.
- Do not commit unless the user separately requests it.

---

### Task 1: Lock common-month and strict-coverage behavior

**Files:**
- Modify: `backend/tests/core_finance/test_macro_leading_indicator.py`
- Modify: `tests/test_leading_indicator_missing_months.py`
- Modify: `backend/app/core_finance/macro/leading_indicator.py`

**Step 1: Add failing tests**

Cover:

1. A July report with all macro monthly legs in June and daily legs in June/July selects `as_of_month=2026-06`.
2. July market observations appear only in `latest_available_component_evidence`; they do not enter the June score.
3. A cross-month forward-filled value is not a real observation.
4. Daily term and credit legs use the last same-day computable observation within the selected month.
5. If no month contains all six components, return `unavailable`, `lei_index=None`, `economic_state="数据不足"`, and no directional primary result.
6. All paths preserve `observation_only=true` and `formal_use_allowed=false`.

Run:

```powershell
python -m pytest tests/test_leading_indicator_missing_months.py backend/tests/core_finance/test_macro_leading_indicator.py -q --tb=short
```

Expected before implementation: new tests fail on missing `as_of_month`, mixed-month scoring, or partial LEI output.

**Step 2: Implement true monthly observations**

In `leading_indicator.py`:

- Build per-component observations keyed by each value's real `*_source_date` month.
- Deduplicate forward-filled copies by source date.
- For each component/month retain the latest real source date not after `report_date` or month-end.
- Compute the intersection across PMI, M2 YoY, social-financing YoY, term spread, credit spread, and Brent; select its latest month.
- Do not fall back to partial reweighting when the intersection is empty.
- Keep existing Decimal formulas, weights, and state thresholds unchanged.

**Step 3: Add alignment evidence**

Return:

- `as_of_month`
- `alignment_policy="latest_common_computable_month"`
- `alignment_lag_months`
- `available_component_count=6` and `component_count=6` for a scored result
- `component_evidence` with source date/month, value, unit, unit status, and whether used
- `latest_available_component_evidence` for newer excluded observations

Warnings:

- `LEI_AS_OF_MONTH_LAGGED`
- `LEI_NEWER_COMPONENT_DATA_EXCLUDED`
- `LEI_NO_COMMON_COMPUTABLE_MONTH`
- `LEI_UNIT_CONTRACT_UNFROZEN`
- `PIT_METADATA_UNAVAILABLE`
- Retain relevant missing-history warnings.

**Step 4: Verify**

Run the focused tests and Ruff:

```powershell
python -m pytest tests/test_leading_indicator_missing_months.py backend/tests/core_finance/test_macro_leading_indicator.py -q --tb=short
python -m ruff check backend/app/core_finance/macro/leading_indicator.py tests/test_leading_indicator_missing_months.py backend/tests/core_finance/test_macro_leading_indicator.py
```

Expected: all pass.

---

### Task 2: Implement 12-month primary and 24-month shadow windows

**Files:**
- Modify: `backend/app/core_finance/macro/leading_indicator.py`
- Modify: `backend/tests/core_finance/test_macro_leading_indicator.py`
- Modify: `tests/test_leading_indicator_missing_months.py`

**Step 1: Add failing window tests**

Cover:

- Primary M2/social-financing/commodity histories use only the 12 calendar months strictly before `as_of_month`.
- Missing months stay `None` and reduce `used`, not `total`.
- Rows older than 12 months cannot change the primary LEI.
- The 24-month shadow may change only history-dependent component scores and carries explicit `shadow=true`.
- Rows after `as_of_month` cannot affect either result.

**Step 2: Implement bounded windows**

- Replace unbounded history means with explicit 12-month slices.
- Compute a nested 24-month shadow result without duplicating the full capability envelope.
- Return primary and shadow window start/end, used/total counts, and coverage.
- Replace `LEI_LOOKBACK_UNGOVERNED` with an owner-approved observation-window marker; continue to disclose that PIT/vintage is unavailable.

Suggested shape:

```python
{
    "lookback_months": 12,
    "history_window": {...},
    "shadow_24m": {
        "shadow": True,
        "lookback_months": 24,
        "lei_index": ...,
        "economic_state": ...,
        "component_scores": {...},
        "history_samples": {...},
    },
}
```

**Step 3: Verify**

Run the same focused test and Ruff commands. Expected: all pass.

---

### Task 3: Pair derived values with actual provenance

**Files:**
- Modify: `backend/app/api/routes/macro_toolkit.py`
- Modify: `backend/app/core_finance/macro/helpers.py` only if a local helper cannot safely carry the derived provenance
- Modify: `tests/test_macro_toolkit_scripts.py`
- Modify: `tests/test_leading_indicator_missing_months.py`

**Step 1: Run GitNexus impact**

Before editing each existing symbol, run upstream impact for:

- `_load_macro_wide_rows`
- `_capability_input_evidence_item`
- `enrich_wide_with_curve_market_fields` if modified

Warn before proceeding if any result is HIGH or CRITICAL.

**Step 2: Add failing provenance tests**

Cover:

- Term spread value, date, unit, transform, and 1Y/10Y legs are from the same observation date.
- Credit spread value, date, unit, transform, and AAA/GOV 3Y legs are from the same observation date.
- `input_evidence` does not combine a July value with an April alias date.
- Derived provenance is replaced atomically when a value is enriched.
- Existing Merrill Clock, economic-cycle, and cross-market consumers ignore the M10 provenance sidecar and keep their behavior.

**Step 3: Implement page-local provenance**

- Keep the shared wide numeric fields compatible.
- Attach a page-local `_provenance` sidecar or equivalent scoped structure for M10.
- For source series preserve source date, series ID, vendor, unit, frequency, and available version fields when present.
- For derived spreads preserve transform and both legs.
- Treat unresolved social-financing and AAA-leg units as provisional observation-only metadata; emit explicit warnings and never set formal use.
- Make `_capability_input_evidence_item` take value/date/source from one matching observation.

**Step 4: Verify**

```powershell
python -m pytest tests/test_macro_toolkit_scripts.py -q --tb=short -k "leading_indicator or capability_input_evidence or macro_toolkit_api_exposes_analysis_payload"
python -m pytest tests/test_macro_observation_capabilities.py -q --tb=short
python -m ruff check backend/app/api/routes/macro_toolkit.py backend/app/core_finance/macro/helpers.py tests/test_macro_toolkit_scripts.py
```

Expected: relevant tests pass with no behavior regression in other observation capabilities.

---

### Task 4: Live tie-out, documentation, and review

**Files:**
- Modify: `docs/strategy_contracts/macro_strategy_research.md`
- Modify: `docs/strategy_contracts/macro_strategy_p0_owner_signoff_packet_2026-07-19.md`
- Add or modify a focused golden sample only if the repository's existing catalog pattern supports it without new infrastructure.

**Step 1: Live read-only tie-out**

For `report_date=2026-07-20`, verify:

- `as_of_month=2026-06`
- six components are used
- July term/credit/oil observations are disclosed but excluded
- primary lookback is 12 months
- shadow lookback is 24 months
- result remains degraded/non-formal while unit and PIT warnings remain
- no 1/6 commodity-only LEI is exposed

Record exact observed values rather than forcing previously estimated values if current DuckDB data changed.

**Step 2: Update documentation**

Document:

- Common-month policy and daily month-end mapping.
- 12-month primary / 24-month shadow decision.
- Unit-status and PIT limitations.
- Current live tie-out and warning set.
- No change to formal admission.

**Step 3: Run final checks**

```powershell
python -m pytest tests/test_leading_indicator_missing_months.py backend/tests/core_finance/test_macro_leading_indicator.py -q --tb=short
python -m pytest tests/test_macro_toolkit_scripts.py -q --tb=short -k "leading_indicator or macro_toolkit_api_exposes_analysis_payload"
python -m ruff check backend/app/api/routes/macro_toolkit.py backend/app/core_finance/macro/leading_indicator.py tests/test_leading_indicator_missing_months.py backend/tests/core_finance/test_macro_leading_indicator.py
git diff --check
```

Run `npm run debt:audit` only if frontend files, API clients, mocks, adapters, formatters, selectors, or pages are touched.

**Step 4: Reviews**

- Spec reviewer confirms strict 6/6, common-month, bounded windows, provenance pairing, and non-formal boundaries.
- Code-quality reviewer checks date arithmetic, Decimal math, null/zero handling, shared-consumer compatibility, and test quality.
- Resolve all Important or higher findings before completion.

