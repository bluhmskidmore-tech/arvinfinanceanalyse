# GS-PNL-ATTR-WB-A Assertions

## Source

- `docs/page_contracts.md` -> `PAGE-PNL-ATTR-WB-001`
- `docs/metric_dictionary.md` -> `MTR-PAT-001` through `MTR-PAT-006`
- `backend/app/api/routes/pnl_attribution.py`
- `backend/app/services/pnl_attribution_service.py`
- `backend/app/core_finance/pnl_attribution/workbench.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200`.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "pnl_attribution.volume_rate"`.
- `result_meta.formal_use_allowed == true`.
- `result_meta.source_version == "sv_pnl_by_business_gs_attr_wb"`.
- `result_meta.rule_version == "rv_pnl_attribution_workbench_v1"`.
- `result_meta.cache_version == "cv_pnl_attribution_workbench_v1"`.
- `result_meta.quality_flag == "ok"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.source_surface == "formal_attribution"`.
- `result_meta.as_of_date == "2026-04-30"`.
- `result_meta.filters_applied.requested_report_date == "2026-04-30"`.
- `result_meta.filters_applied.previous_report_date == "2026-03-31"`.
- `result_meta.tables_used == ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily"]`.
- `result.current_period == "2026-04"`.
- `result.previous_period == "2026-03"`.
- `result.compare_type == "mom"`.
- `result.has_previous_data == true`.

## Frozen Values

- `MTR-PAT-001`: `result.total_current_pnl.raw == 120.0`.
- `MTR-PAT-002`: `result.total_previous_pnl.raw == 80.0`.
- `MTR-PAT-003`: `result.items[0].current_yield_pct.raw == 0.12`.
- `MTR-PAT-004`: `result.items[0].previous_yield_pct.raw == 0.1`.
- `MTR-PAT-005`: `result.total_volume_effect.raw == 20.0`.
- `MTR-PAT-006`: `result.total_rate_effect.raw` displays as `+16.00`.
- `result.total_interaction_effect.raw` displays as `+4.00`.
- `result.items[0].category == "business_cd"`.
- Numeric values remain backend-owned `Numeric` objects with `raw`, `unit`, `display`, `precision`, and `sign_aware`.

## Boundary

- This sample freezes the `GET /api/pnl-attribution/volume-rate` workbench DTO for `PAGE-PNL-ATTR-WB-001`.
- It does not freeze every `/api/pnl-attribution/*` advanced or Campisi surface.
- It does not replace `/api/pnl/overview` formal PnL truth.
- It does not replace the executive analytical overlay `/ui/pnl/attribution` or `GS-EXEC-PNL-ATTR-A`.
- It does not approve page-level closure by itself; direct governance records, catalog/date evidence, and business-owner review remain separate.
