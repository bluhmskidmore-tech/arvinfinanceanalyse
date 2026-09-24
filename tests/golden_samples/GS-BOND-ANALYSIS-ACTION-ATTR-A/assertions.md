# GS-BOND-ANALYSIS-ACTION-ATTR-A Assertions

## Source

- `docs/page_contracts.md` -> `PAGE-BOND-ANALYSIS-001`
- `docs/metric_dictionary.md` -> `MTR-BOND-ACT-001` through `MTR-BOND-ACT-006`
- `backend/app/api/routes/bond_analytics.py`
- `backend/app/services/bond_analytics_service.py`
- `backend/app/core_finance/action_attribution.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when exercised through the authorized route contract.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "analytical"`.
- `result_meta.result_kind == "bond_analytics.action_attribution"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.source_version == "sv_bond_analysis_action_attr_gs_a"`.
- `result_meta.rule_version == "rv_bond_analytics_formal_materialize_v2"`.
- `result_meta.cache_version == "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v2"`.
- `result_meta.quality_flag == "warning"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.source_surface == "bond_analytics"`.
- `result.report_date == "2026-03-31"`.
- `result.period_type == "MoM"`.
- `result.period_start == "2026-03-01"`.
- `result.period_end == "2026-03-31"`.

## Frozen Values

- `MTR-BOND-ACT-001`: `result.total_actions == 1`.
- `MTR-BOND-ACT-002`: `result.total_pnl_from_actions == "1250000.00000000"` in yuan.
- `MTR-BOND-ACT-003`: `result.period_start_duration == "3.00000000"`.
- `MTR-BOND-ACT-004`: `result.period_end_duration == "3.20000000"`.
- `MTR-BOND-ACT-005`: `result.duration_change_from_actions == "0.20000000"`.
- `MTR-BOND-ACT-006`: `result.period_start_dv01 == null` and `result.period_end_dv01 == null`; the current snapshot-diff implementation has no action-level DV01 input and must not emit synthetic zeroes.
- `result.available_components == ["snapshot_diff", "capital_gain_517_allocation"]`.
- `result.status == "partial"`.
- `result.missing_inputs == ["action_level_dv01", "independent_accounting_pnl"]`.
- `result.blocked_components == ["dv01_attribution", "independent_accounting_pnl_reconciliation"]`.
- `result.warnings` includes `ACTION_ATTRIBUTION_DV01_UNAVAILABLE` and `ACTION_ATTRIBUTION_ACCOUNTING_PNL_DERIVED_COPY`.
- `pnl_accounting` is currently a derived copy of `pnl_economic`; the sample freezes that DTO behavior but does not certify it as an independently reconciled accounting result.

## Boundary

- This sample freezes route-scoped page DTO evidence for `GET /api/bond-analytics/action-attribution`.
- It is bound to `/bond-analysis` and `PAGE-BOND-ANALYSIS-001`.
- It does not certify `/bond-dashboard`, `PAGE-BOND-001`, `GS-BOND-HEADLINE-A`, or `MTR-BOND-001` through `MTR-BOND-004`.
- It does not approve fixed-income action-attribution, DV01, duration, KRD, yield/YTM, credit-spread, holdings, or accounting-class values as formal metric truth.
- It preserves `formal_use_allowed=false`; page-level governance validation, manual audit review, and business-owner approval remain required before closure.
- The sample remains `captured-awaiting-approval`; these corrections do not constitute approval.
