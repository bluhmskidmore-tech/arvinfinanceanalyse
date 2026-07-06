# GS-CASHFLOW-PROJECTION-A Assertions

## Source

- `docs/live_route_maturity.md` -> `GAP-CASHFLOW-PROJECTION-PAGE`
- `docs/metric_dictionary.md` -> `MTR-CFP-001` through `MTR-CFP-004`
- `backend/app/api/routes/cashflow_projection.py`
- `backend/app/services/cashflow_projection_service.py`
- `backend/app/core_finance/cashflow_projection.py`
- `tests/test_cashflow_projection.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when an explicit `cashflow_projection:read` scope is available.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "analytical"`.
- `result_meta.result_kind == "cashflow_projection.overview"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.source_version == "sv_cashflow_projection_gs_a_asset__sv_cashflow_projection_gs_a_liability"`.
- `result_meta.rule_version == "rv_cashflow_projection_gs_a"`.
- `result_meta.cache_version == "cv_cashflow_projection_read_v1"`.
- `result_meta.quality_flag == "warning"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.requested_report_date == "2026-04-30"`.
- `result_meta.resolved_report_date == "2026-04-30"`.
- `result_meta.as_of_date == "2026-04-30"`.
- `result_meta.date_basis == "cashflow_projection_report_date"`.
- `result_meta.source_surface == "cashflow"`.
- `result_meta.tables_used == ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"]`.
- `result_meta.evidence_rows == 2`.

## Frozen Values

- `MTR-CFP-001`: `result.duration_gap.display == "+0.30"` (textbook gap `D_A - (L/A) * D_L`).
- `MTR-CFP-002`: `result.asset_duration.display == "0.50"`.
- `MTR-CFP-003`: `result.liability_duration.display == "0.25"`.
- `MTR-CFP-004`: `result.rate_sensitivity_1bp.unit == "yuan"` and `display == "-0.03"` (equity value change for a +1bp rate move; positive equity duration implies a negative sensitivity).
- `result.warnings` includes the liability remaining-term proxy disclosure.
- `result.reinvestment_risk_12m.display == "100.00%"`.
- `result.monthly_buckets[3].year_month == "2026-07"` and `net_cashflow.display == "-800.00"`.
- `result.monthly_buckets[6].year_month == "2026-10"` and `net_cashflow.display == "+1,000.00"`.
- `result.top_maturing_assets_12m[0].instrument_code == "CF-BOND-001"`.
- Numeric values remain backend-owned `Numeric` objects with `raw`, `unit`, `display`, `precision`, and `sign_aware`.

## Boundary

- This sample freezes the `GET /api/cashflow-projection` candidate page DTO for `GAP-CASHFLOW-PROJECTION-PAGE`.
- It preserves `formal_use_allowed=false`; `MTR-CFP-001` through `MTR-CFP-004` remain candidate display metrics with pending confirmation.
- It does not replace formal liquidity, PAGE-RISK-001 formal risk truth, PAGE-BALANCE-001 balance truth, or formal PnL truth.
- Direct governance review, catalog/date evidence, manual audit closure, and business-owner approval remain separate.
