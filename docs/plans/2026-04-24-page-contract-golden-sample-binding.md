# Page Contract And Golden Sample Binding

## Status

- date: 2026-04-24
- scope: read-only docs/sample binding plan
- purpose: align page contracts, metric dictionary, golden sample catalog, and executable sample tests

## Existing Assets

- `docs/page_contracts.md`
  - main page-level contracts
  - includes page purpose, sections, endpoint/DTO, metric mapping, state contract, and sample mapping sections
- `docs/metric_dictionary.md`
  - current metric IDs, basis, source fields, page surfaces, tests
  - does not yet consistently fill `sample_scope` per metric
- `docs/golden_sample_plan.md`
  - describes sample governance and Batch A scope
- `docs/golden_sample_catalog.md`
  - catalog of sample status and gaps
- `tests/golden_samples/`
  - executable sample packages
- `tests/test_golden_samples_capture_ready.py`
  - sample package structure and validator matrix

## Current Sample Directories

Current observed sample packages:

- `GS-BAL-OVERVIEW-A`
- `GS-BAL-WORKBOOK-A`
- `GS-PNL-OVERVIEW-A`
- `GS-PNL-DATA-A`
- `GS-BRIDGE-A`
- `GS-BRIDGE-WARN-B`
- `GS-RISK-A`
- `GS-RISK-WARN-B`
- `GS-EXEC-OVERVIEW-A`
- `GS-EXEC-SUMMARY-A`
- `GS-EXEC-PNL-ATTR-A`
- `GS-PROD-CAT-PNL-A`

## Known Binding Gaps

### Resolved Verification Gap

Observed on 2026-04-24:

```powershell
python -m pytest -q tests/test_golden_samples_capture_ready.py
```

Result:

- initial result: `13 passed`, `1 failed`
- initial failing sample: `GS-EXEC-OVERVIEW-A`
- resolved result after sample JSON/assertion update: `14 passed`

Resolved shape:

- actual executive overview metric rows include `caliber_label`
- frozen `tests/golden_samples/GS-EXEC-OVERVIEW-A/response.json` now includes:
  - `aum.caliber_label = "本币资产口径"`
  - `yield.caliber_label = null`
  - `nim.caliber_label = null`
  - `dv01.caliber_label = null`
- `tests/golden_samples/GS-EXEC-OVERVIEW-A/assertions.md` now records those expectations

This was sample/catalog alignment work, not evidence that the system boundary should broaden.

### Product Category PnL

`GS-PROD-CAT-PNL-A` exists and has a dedicated truth contract under `docs/pnl/`, but the main `docs/page_contracts.md` does not yet have a first-class `PAGE-PROD-CAT-PNL-001` entry.

Recommended follow-up:

- add `PAGE-PROD-CAT-PNL-001` to `docs/page_contracts.md`
- bind it to:
  - `docs/pnl/product-category-page-truth-contract.md`
  - `docs/pnl/product-category-closure-checklist.md`
  - `GS-PROD-CAT-PNL-A`
  - `tests/test_golden_samples_capture_ready.py`

### Warning Profile Samples

`GS-BRIDGE-WARN-B` and `GS-RISK-WARN-B` are useful degraded-state samples. They should be explicitly documented as warning profile samples, not treated as failed samples.

Recommended follow-up:

- align `docs/golden_sample_plan.md` and `docs/golden_sample_catalog.md`
- ensure page contracts mention warning/degraded samples where relevant

### Bond Headline Candidate

`GS-BOND-HEADLINE-A` is blocked by contract gap. It should remain candidate/blocked until metric dictionary GAPs for bond headline/risk are closed **and** a real `tests/golden_samples/GS-BOND-HEADLINE-A/` directory (four files) exists **and** that sample is listed in `tests/test_golden_samples_capture_ready.py`. Page contract + mapping work alone does not lift blocked status.

Recommended follow-up:

- do not fabricate an empty sample folder to satisfy docs
- finish `GAP-BOND-DASH-*` / mapping work first, then add the on-disk package and gate registration when ready

### Metric Dictionary Sample Scope

`docs/metric_dictionary.md` defines page/test anchors, but `sample_scope` is not consistently populated.

Recommended follow-up:

- fill `sample_scope` only for active P0/P1 metrics that already have a sample package
- avoid inventing samples for metrics that are still candidate or outside current boundary

## Cursor Task Pack

### Task 1 - Product Category Main Page Contract

Write scope:

- `docs/page_contracts.md`

Read first:

- `docs/pnl/product-category-page-truth-contract.md`
- `docs/pnl/product-category-closure-checklist.md`
- `tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md`

Goal:

- Add a compact `PAGE-PROD-CAT-PNL-001` section and bind `GS-PROD-CAT-PNL-A`.

Do not:

- change code
- change sample JSON
- promote unrelated PnL attribution or executive routes

### Task 2 - Golden Sample Plan/Catalog Alignment

Write scope:

- `docs/golden_sample_plan.md`
- `docs/golden_sample_catalog.md`

Goal:

- Align the documented sample list with the 12 current sample directories and `test_golden_samples_capture_ready.py`.
- Keep `GS-EXEC-OVERVIEW-A` documented as aligned around `caliber_label`.

Do not:

- change sample responses unless the actual runtime shape is verified and the response update is intentionally approved
- add new sample dirs

### Task 3 - Metric Dictionary `sample_scope`

Write scope:

- `docs/metric_dictionary.md`

Goal:

- Add sample references only for metrics already covered by existing active samples.

Do not:

- invent new metric IDs
- broaden current cutover scope

## Verification

Docs-only verification:

```powershell
rg -n "GS-PROD-CAT-PNL-A|GS-BRIDGE-WARN-B|GS-RISK-WARN-B|GS-BOND-HEADLINE-A|sample_scope|PAGE-PROD-CAT" docs tests
```

Sample structure verification:

```powershell
python -m pytest -q tests/test_golden_samples_capture_ready.py
```
