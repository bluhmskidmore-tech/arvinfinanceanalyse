# GS-BOND-HEADLINE-A Assertions

## Source

- `tests/test_bond_dashboard_api_contract.py`
- `backend/app/api/routes/bond_dashboard.py`
- `backend/app/services/bond_dashboard_service.py`
- `frontend/src/features/bond-dashboard/components/HeadlineKpis.tsx`
- `docs/page_contracts.md`

## Required assertions

- HTTP status is `200`.
- The top-level envelope contains `result_meta`, `result`, and `data_source`.
- `data_source == "bond_analytics_facts"`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "bond_dashboard.headline_kpis"`.
- `result_meta.formal_use_allowed == true`.
- `result_meta.source_version == "sv"`.
- `result_meta.vendor_version == "vv_none"`.
- `result_meta.rule_version == "rv_bond_analytics_formal_materialize_v1"`.
- `result_meta.cache_version == "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1"`.
- `result_meta.quality_flag == "ok"`.
- `result_meta.vendor_status == "ok"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.scenario_flag == false`.
- `result_meta.source_surface == "bond_analytics"`.
- `result.report_date == "2026-03-31"`.
- `result.prev_report_date == "2026-03-30"`.
- `result.kpis` and `result.prev_kpis` both exist and expose the same headline key set.

## Headline KPI precision and units

- `total_market_value` is an 8-decimal amount string and the page renders it in `亿`.
- `unrealized_pnl` is an 8-decimal amount string and the page renders it in `亿`.
- `weighted_ytm` is an 8-decimal ratio string and the page renders it in `%`.
- `weighted_duration` is an 8-decimal duration string and the page renders it in `年`.
- `weighted_coupon` is an 8-decimal ratio string and the page renders it in `%`.
- `credit_spread_median` is an 8-decimal ratio string and the page renders it in `%`.
- `total_dv01` is an 8-decimal amount string and the page renders it in `万元`.
- `bond_count` is an integer.

## Frozen values

- `result.kpis.total_market_value == "1000.00000000"`.
- `result.kpis.unrealized_pnl == "0.00000000"`.
- `result.kpis.weighted_ytm == "0.03500000"`.
- `result.kpis.weighted_duration == "5.00000000"`.
- `result.kpis.weighted_coupon == "0.02500000"`.
- `result.kpis.credit_spread_median == "0.04000000"`.
- `result.kpis.total_dv01 == "0.20000000"`.
- `result.kpis.bond_count == 3`.
- `result.prev_kpis.total_market_value == "300.00000000"`.
- `result.prev_kpis.unrealized_pnl == "0.00000000"`.
- `result.prev_kpis.weighted_ytm == "0.03100000"`.
- `result.prev_kpis.weighted_duration == "4.20000000"`.
- `result.prev_kpis.weighted_coupon == "0.02500000"`.
- `result.prev_kpis.credit_spread_median == "0.03500000"`.
- `result.prev_kpis.total_dv01 == "0.12600000"`.
- `result.prev_kpis.bond_count == 2`.

## Null and empty behavior

- On an empty DuckDB, the route still returns HTTP `200` with a formal envelope.
- Empty-state `result.report_date` echoes the requested report date.
- Empty-state `result.kpis` remains present, with zero-valued decimal strings and `bond_count == 0`.
- Empty-state `result.prev_report_date == null`.
- Empty-state `result.prev_kpis == null`.

## Boundary

- This sample freezes the current page-level DTO for `GET /api/bond-dashboard/headline-kpis`.
- It does not approve new `MTR-*` bindings for bond headline or risk fields.
- Cross-page equivalence with balance-analysis totals or risk-tensor metrics remains a separate contract decision.

## Reconciliation

- Keep this sample aligned with `PAGE-BOND-001` in `docs/page_contracts.md`.
- Re-run capture if the bond-dashboard headline DTO shape, unit semantics, or replay seed changes.
