# ADB Architecture Convergence Status

**Goal:** Keep ADB on the repo's fixed layering `api -> services -> (repositories / core_finance)` while preserving the existing analytical contract.

## Current State

As of 2026-04-16, the main structural convergence work is already in place:

- `backend/app/repositories/adb_repo.py` exists and owns formal-fact reads plus DataFrame shaping.
- `backend/app/core_finance/adb_analysis.py` exists and owns pure ADB payload building.
- `backend/app/services/adb_analysis_service.py` has been reduced to orchestration plus analytical envelope assembly.
- The single-snapshot downgrade contract is preserved:
  - `result_meta.quality_flag == "warning"`
  - comparison payload includes the `single snapshot` detail text

## Verified Coverage

The current focused backend suite is:

```powershell
python -m pytest tests/test_adb_repo.py tests/test_adb_core_finance.py tests/test_adb_service_boundaries.py tests/test_adb_analysis_api.py -q
```

This suite now covers:

- repository output shape and version propagation
- core-finance comparison contract
- service-layer delegation boundaries
- API envelope contract and alias compatibility

## Remaining Work

The remaining work is smaller than the original plan and should not recreate already-extracted layers.

### 1. Freeze Daily And Monthly Core-Finance Builders

Add direct unit coverage for:

- `build_adb_daily_payload(...)`
- `build_adb_monthly_payload(...)`

These tests should assert payload shape and a few high-signal contract fields:

- daily summary totals
- daily trend output
- daily breakdown rows
- monthly asset/liability rates
- monthly MoM fields
- monthly YTD NIM

### 2. Keep The Plan Aligned With The Live Codebase

Do not re-open completed extraction steps. Future work should treat:

- repo extraction as done
- core-finance extraction as done
- service delegation as done

### 3. Optional Adjacent Regression Pass

If ADB work expands again, run adjacent checks:

```powershell
python -m pytest tests/test_balance_analysis_api.py tests/test_no_finance_logic_in_api.py -q
```

## Risks To Watch

- `asset_yield` in comparison now follows the frozen contract enforced by the test suite; if business semantics change, update tests first.
- Repository DataFrame schema is still a coupling point between `adb_repo.py` and `adb_analysis.py`; any column-shape changes must be reflected in direct core-finance tests.

## Commit Guidance

If this work is committed later, use the repo's Lore commit protocol from `AGENTS.md` instead of plain one-line commit examples.
