# GS-CONCENTRATION-MONITOR-A Assertions

## Source

- `docs/live_route_maturity.md` -> `PAGE-CONC-001`
- `docs/metric_dictionary.md` -> `MTR-CON-001` through `MTR-CON-004`
- `backend/app/api/routes/bond_analytics.py`
- `backend/app/services/bond_analytics_service.py`
- `backend/app/core_finance/bond_analytics/read_models.py`
- `tests/test_bond_analytics_service.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when an explicit `bond_analytics:read` scope is available.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "analytical"`.
- `result_meta.result_kind == "bond_analytics.credit_spread_migration"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.source_version == "sv_concentration_monitor_gs_a"`.
- `result_meta.rule_version == "rv_bond_analytics_formal_materialize_v1"`.
- `result_meta.cache_version == "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1"`.
- `result_meta.quality_flag == "warning"`.
- `result_meta.vendor_status == "vendor_unavailable"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.requested_report_date == "2026-03-31"`.
- `result_meta.resolved_report_date == "2026-03-31"`.
- `result_meta.as_of_date == "2026-03-31"`.
- `result_meta.date_basis == "bond_analytics_report_date"`.
- `result_meta.source_surface == "bond_analytics"`.
- `result_meta.tables_used == ["fact_formal_bond_analytics_daily"]`.
- `result_meta.evidence_rows == 3`.

## Frozen Values

- `MTR-CON-001`: `result.concentration_by_issuer.hhi == "0.53125000"`.
- `MTR-CON-002`: `result.concentration_by_issuer.top5_concentration == "1.00000000"`.
- `MTR-CON-003`: `result.credit_weight == "0.80000000"`.
- `MTR-CON-004`: `result.rating_aa_and_below_weight == "0.30000000"`.
- `result.credit_bond_count == 2`.
- `result.credit_market_value == "160.00000000"`.
- `result.spread_dv01 == "7.00000000"`.
- `result.weighted_avg_spread == "0.00000000"` because credit-spread curve inputs are intentionally unavailable in this warning sample.
- `result.concentration_by_issuer.top_items[0].name == "Issuer A"`.
- `result.concentration_by_rating.top_items[1].name == "AA"`.
- `result.spread_scenarios.length == 4`.
- Warning output includes missing `aaa_credit` and treasury curve messages.

## Boundary

- This sample freezes the `GET /api/bond-analytics/credit-spread-migration` candidate page DTO for `PAGE-CONC-001`.
- It preserves `formal_use_allowed=false`; `MTR-CON-001` through `MTR-CON-004` remain candidate display metrics with pending confirmation.
- It does not replace PAGE-RISK-001 formal risk truth, `/bond-analysis` action-attribution evidence, formal fixed-income metric truth, or certified concentration-limit approval.
- Direct governance review, catalog/date evidence, manual audit closure, and business-owner approval remain separate.
