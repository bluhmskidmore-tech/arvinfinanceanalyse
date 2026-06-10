# GS-AVERAGE-BALANCE-A Assertions

## Source

- `docs/live_route_maturity.md` -> `GAP-AVERAGE-BALANCE-PAGE`
- `docs/metric_dictionary.md` -> `MTR-ADB-001` and `MTR-ADB-002` daily sample binding; `MTR-ADB-003` remains monthly pending with `bound_sample_id=none`
- `backend/app/api/routes/adb_analysis.py`
- `backend/app/services/adb_analysis_service.py`
- `backend/app/core_finance/adb_analytics.py`
- `tests/test_adb_analysis_api.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when an explicit `adb_analysis:read` scope is available.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "analytical"`.
- `result_meta.result_kind == "adb.daily"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.vendor_version == "vv_none"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.scenario_flag == false`.
- `result_meta.tables_used == ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"]`.

## Frozen Values

- `MTR-ADB-001`: `result.summary.total_avg_assets` is frozen from the deterministic fixture-backed `GET /api/analysis/adb` response.
- `MTR-ADB-002`: `result.summary.total_avg_liabilities` is frozen from the deterministic fixture-backed response.
- `result.summary.end_spot_assets` and `result.summary.end_spot_liabilities` are frozen for the same candidate analytical DTO.
- `result.trend` and `result.breakdown` are frozen to protect date, category, side, and amount semantics.

## Boundary

- This sample freezes the `GET /api/analysis/adb` candidate page DTO for `GAP-AVERAGE-BALANCE-PAGE`.
- It preserves `formal_use_allowed=false`; `MTR-ADB-001` through `MTR-ADB-003` remain candidate display metrics with pending confirmation.
- It does not replace `PAGE-BALANCE-001` formal balance truth, approve ADB metrics, approve monthly NIM, approve manual audit closure, or capture business-owner approval.
