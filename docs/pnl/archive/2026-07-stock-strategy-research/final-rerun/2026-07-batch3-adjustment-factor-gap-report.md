# 2026-07 Batch 3 Adjustment Factor Gap Report

- status: research_only
- clean_path_count: 84
- clean_execution_row_count: 93

## Adjustment Factor Coverage

- path_count: 811
- total_path_rows: 20259
- missing_adjustment_factor_rows: 3564
- missing_adjustment_factor_ratio: 0.175922
- affected_symbol_date_count: 3246

## Top Missing Symbols

| stock_code | missing_rows | first_date | last_date |
|---|---:|---|---|
| 000823.SZ | 36 | 2024-11-14 | 2025-01-24 |
| 300971.SZ | 36 | 2025-03-21 | 2025-04-24 |
| 600693.SH | 33 | 2025-01-02 | 2025-01-24 |
| 600530.SH | 25 | 2025-01-02 | 2025-06-26 |
| 002165.SZ | 24 | 2025-04-01 | 2025-04-24 |
| 603868.SH | 24 | 2025-01-02 | 2025-01-24 |
| 603893.SH | 24 | 2025-01-02 | 2025-01-24 |
| 002369.SZ | 23 | 2025-01-02 | 2025-01-24 |
| 601869.SH | 22 | 2025-01-02 | 2025-09-04 |
| 600121.SH | 21 | 2025-10-28 | 2025-11-21 |

## Sensitivity Excluding Missing Adjustment Paths

- status: ready
- risk_0p005_return_delta: -0.393019
- risk_0p005_mdd_delta: -0.045146
- risk_0p005_still_beats_fixed_20d: False

Fixed 20d metrics:
{"annual_turnover": 2.497571, "avg_slot_utilization": 0.243028, "cagr": 0.753735, "confirm_days": null, "cumulative_return": 0.745934, "daily_sharpe": 3.268307, "empty_day_ratio": 0.657371, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 68, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 0.729084, "exposure_fallback_days": 183, "max_drawdown": 0.063664, "max_entry_premium": null, "max_single_name_weight": 0.223885, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 0, "risk_budget_hit_rate": null, "risk_budget_trade_count": 0, "risk_per_trade": null, "sample_days": 250, "single_name_cap": null, "sizing": "equal_weight", "stop_ref_fallback": 0, "terminal_value": 174.59341, "vol_target": null}

Risk-budget 0.005 metrics:
{"annual_turnover": 0.935004, "avg_slot_utilization": 0.243028, "cagr": 0.35619, "confirm_days": null, "cumulative_return": 0.352915, "daily_sharpe": 3.997251, "empty_day_ratio": 0.657371, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 68, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 0.729084, "exposure_fallback_days": 183, "max_drawdown": 0.018518, "max_entry_premium": null, "max_single_name_weight": 0.16089, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 14, "risk_budget_hit_rate": 0.875, "risk_budget_trade_count": 16, "risk_per_trade": 0.005, "sample_days": 250, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 135.29149, "vol_target": null}
