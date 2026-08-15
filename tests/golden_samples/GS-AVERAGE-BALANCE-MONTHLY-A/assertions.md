# GS-AVERAGE-BALANCE-MONTHLY-A Assertions

## Source

- `docs/live_route_maturity.md` -> `PAGE-ADB-001`
- `docs/metric_dictionary.md` -> `MTR-ADB-003`
- `backend/app/api/routes/adb_analysis.py`
- `backend/app/services/adb_analysis_service.py`
- `backend/app/core_finance/adb_analytics.py`
- `tests/test_adb_analysis_api.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when an explicit `adb_analysis:read` scope is available.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "analytical"`.
- `result_meta.result_kind == "adb.monthly"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.vendor_version == "vv_none"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.scenario_flag == false`.
- `result_meta.filters_applied == {"year": 2025, "accounting_basis_currency": "CNX"}`; `CNX` is the governed CNY accounting-basis code, not a source-currency conversion claim.
- `result_meta.tables_used == ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily", "product_category_pnl_canonical_fact"]`; the third relation supplies governed basis/calibration evidence and does not replace the two ADB balance facts.

## Frozen Values

- `MTR-ADB-003`: `result.ytd_nim` is frozen from the deterministic fixture-backed `GET /api/analysis/adb/monthly?year=2025` response.
- The selected monthly DTO fields freeze `year`, one `2025-12` month row, average asset/liability balances, end-spot balances, MoM null semantics, weighted rates, NIM, YTD averages, YTD rates, and `unit`.
- Category display text is intentionally not frozen by this sample; it is page presentation evidence, not the stable owner-approved metric definition.

## Boundary

- This sample freezes the `GET /api/analysis/adb/monthly` candidate page DTO for `PAGE-ADB-001`.
- It preserves `formal_use_allowed=false`; `MTR-ADB-001` through `MTR-ADB-003` remain candidate display metrics with pending confirmation.
- It does not replace `PAGE-BALANCE-001` formal balance truth, approve ADB metrics, approve manual audit closure, or capture business-owner approval.
