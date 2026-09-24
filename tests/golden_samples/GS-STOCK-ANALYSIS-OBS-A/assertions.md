# GS-STOCK-ANALYSIS-OBS-A Assertions

## Source

- `docs/audits/2026-06-06-stock-analysis-gate-i-lane.md`
- `docs/page_contracts.md` -> `GAP-STOCK-ANALYSIS-PAGE`
- `docs/metric_dictionary.md` -> sample-scope observational boundary
- `backend/app/api/routes/market_data_livermore.py`
- `backend/app/services/market_data_livermore_service.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when exercised through the authorized route contract.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "analytical"`.
- `result_meta.result_kind == "market_data.livermore"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.source_version == "sv_stock_analysis_obs_gs_a"`.
- `result_meta.vendor_version == "vv_choice_stock_obs_gs_a"`.
- `result_meta.rule_version == "rv_livermore_strategy_v1"`.
- `result_meta.cache_version == "cv_livermore_strategy_v1"`.
- `result_meta.quality_flag == "warning"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.source_surface == "market_data"`.
- `result_meta.filters_applied.requested_as_of_date == "2026-04-03"`.
- `result_meta.filters_applied.as_of_date == "2026-04-03"`.
- `result_meta.tables_used == ["fact_choice_macro_daily"]`.
- `result_meta.evidence_rows == 3`.
- `result.as_of_date == "2026-04-03"`.
- `result.requested_as_of_date == "2026-04-03"`.
- `result.strategy_name == "Livermore A-Share Defended Trend"`.
- `result.basis == "analytical"`.

## Frozen Observations

- `result.market_gate.state == "PENDING_DATA"`.
- `result.market_gate.passed_conditions == 0`.
- `result.market_gate.required_conditions == 4`.
- `result.supported_outputs == ["market_gate"]`.
- `result.unsupported_outputs` includes `sector_rank`, `stock_candidates`, `uptrend_momentum_candidates`, `fresh_trend_watchlist`, `mean_reversion_candidates`, `factor_screen_candidates`, `theme_breakout`, `hybrid_fusion`, and `risk_exit`.
- `result.rule_readiness` preserves the four keys `market_gate`, `sector_rank`, `stock_pivot`, and `risk_exit`.
- `result.data_gaps` preserves missing or partial input families for broad-index history, macro inputs, stock universe, sector strength, limit-up quality, and position risk.

## Boundary

- This sample freezes route-scoped page DTO evidence for `GET /ui/market-data/livermore`.
- It is bound to `/stock-analysis` and `GAP-STOCK-ANALYSIS-PAGE`.
- It does not create `PAGE-STOCK-*` contracts or `MTR-STOCK-*` metrics.
- It does not approve Livermore candidates, sector ranking, signal confluence, strategy scores, optimization diagnostics, or proxy backtests as formal stock-analysis truth.
- It does not authorize trading instructions, execution approval, allocation advice, or position-change commands.
- It preserves `formal_use_allowed=false`; page-level governance validation, manual audit review, golden approval, and business-owner approval remain required before closure.
