# 2026-07 Batch 3 Risk-Budget Robustness Report

- status: research_only
- signal_kind: stock_candidate
- execution_row_count: 826
- recommendation: research_only

## Variant Metrics

| variant | cumulative_return | cagr | max_drawdown | daily_sharpe | sortino | calmar | annual_turnover | avg_exposure | max_single_name_weight | avg_position_count | win_rate | avg_winner | avg_loser | fallback_exposure_ratio | missing_adjusted_path_ratio | liq_200m_pass | liq_200m_fail |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_20d_equal | -0.081789 | -0.054874 | 0.457000 | -0.103494 | -0.169685 | -0.120074 | 4.807474 | 0.472169 | 0.244163 | 3.235602 | 0.353846 | 0.260641 | -0.125209 | 0.000000 | 0.175922 | 0 | 826 |
| fixed_5d_equal | -0.169134 | -0.138995 | 0.319051 | -0.406889 | -0.663455 | -0.435651 | 19.207367 | 0.382361 | 0.265411 | 2.456869 | 0.390625 | 0.124665 | -0.086592 | 0.000000 | 0.175922 | 0 | 826 |
| risk_budget_rpt_0p003 | 0.066028 | 0.043198 | 0.088748 | 0.866791 | 1.654079 | 0.486749 | 1.314141 | 0.099223 | 0.096671 | 3.235602 | 0.369231 | 0.257032 | -0.125486 | 0.000000 | 0.175922 | 0 | 826 |
| risk_budget_rpt_0p005 | 0.106070 | 0.068953 | 0.144072 | 0.843448 | 1.598455 | 0.478601 | 2.175085 | 0.165283 | 0.154808 | 3.235602 | 0.369231 | 0.257032 | -0.125486 | 0.000000 | 0.175922 | 0 | 826 |
| risk_budget_rpt_0p0075 | 0.151284 | 0.097658 | 0.209149 | 0.814799 | 1.531507 | 0.466930 | 3.227112 | 0.247827 | 0.222696 | 3.235602 | 0.369231 | 0.257032 | -0.125486 | 0.000000 | 0.175922 | 0 | 826 |
| risk_budget_rpt_0p01 | 0.147513 | 0.095279 | 0.267600 | 0.653023 | 1.196830 | 0.356050 | 4.027113 | 0.323328 | 0.282004 | 3.235602 | 0.369231 | 0.257032 | -0.125486 | 0.000000 | 0.175922 | 0 | 826 |
| vol_target_0p15_control | -0.045450 | -0.030297 | 0.423506 | -0.008385 | -0.013739 | -0.071539 | 4.638481 | 0.444944 | 0.244163 | 3.235602 | 0.353846 | 0.260641 | -0.125209 | 0.000000 | 0.175922 | 0 | 826 |
| vol_target_0p2_control | -0.075770 | -0.050781 | 0.451623 | -0.087102 | -0.142700 | -0.112441 | 4.786963 | 0.467441 | 0.244163 | 3.235602 | 0.353846 | 0.260641 | -0.125209 | 0.000000 | 0.175922 | 0 | 826 |
| fixed_20d_exposure_matched_to_risk_0p005 | 0.053511 | 0.035080 | 0.129551 | 0.528840 | 0.941829 | 0.270781 | 1.736287 | 0.134015 | 0.062088 | 3.981675 | 0.425000 | 0.221667 | -0.125902 | 0.000000 | 0.175922 | 0 | 826 |

## Bootstrap By Trade Date

{"date_count": 381, "iterations": 300, "mean_increment": 0.158004, "p10_increment": -0.145225, "p50_increment": 0.1199, "p90_increment": 0.507274, "status": "ready"}

## Walk Forward

{"selected_risk_per_trade": 0.003, "split_date": "2025-07-14", "status": "ready", "test_fixed_20d_metrics": {"annual_turnover": 4.022888, "avg_slot_utilization": 0.353927, "cagr": 0.43373, "confirm_days": null, "cumulative_return": 0.724106, "daily_sharpe": 1.916043, "empty_day_ratio": 0.544503, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 382, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 0.0, "exposure_fallback_days": 0, "max_drawdown": 0.154705, "max_entry_premium": null, "max_single_name_weight": 0.385052, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 0, "risk_budget_hit_rate": null, "risk_budget_trade_count": 0, "risk_per_trade": null, "sample_days": 381, "single_name_cap": null, "sizing": "equal_weight", "stop_ref_fallback": 0, "terminal_value": 172.410584, "vol_target": null}, "test_rows": 297, "test_selected_metrics": {"annual_turnover": 0.879533, "avg_slot_utilization": 0.371204, "cagr": 0.101648, "confirm_days": null, "cumulative_return": 0.157617, "daily_sharpe": 2.315979, "empty_day_ratio": 0.513089, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 382, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 0.0, "exposure_fallback_days": 0, "max_drawdown": 0.0257, "max_entry_premium": null, "max_single_name_weight": 0.096671, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 28, "risk_budget_hit_rate": 0.756757, "risk_budget_trade_count": 37, "risk_per_trade": 0.003, "sample_days": 381, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 115.761662, "vol_target": null}, "train_metrics_by_risk": {"0.003": {"annual_turnover": 0.995737, "avg_slot_utilization": 0.540284, "cagr": -0.017823, "confirm_days": null, "cumulative_return": -0.014875, "daily_sharpe": -0.382003, "empty_day_ratio": 0.407583, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 211, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 0.0, "exposure_fallback_days": 0, "max_drawdown": 0.04879, "max_entry_premium": null, "max_single_name_weight": 0.082405, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 18, "risk_budget_hit_rate": 0.6, "risk_budget_trade_count": 30, "risk_per_trade": 0.003, "sample_days": 210, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 98.512501, "vol_target": null}, "0.005": {"annual_turnover": 1.654906, "avg_slot_utilization": 0.540284, "cagr": -0.032031, "confirm_days": null, "cumulative_return": -0.026765, "daily_sharpe": -0.405155, "empty_day_ratio": 0.407583, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 211, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 0.0, "exposure_fallback_days": 0, "max_drawdown": 0.080171, "max_entry_premium": null, "max_single_name_weight": 0.133479, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 18, "risk_budget_hit_rate": 0.6, "risk_budget_trade_count": 30, "risk_per_trade": 0.005, "sample_days": 210, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 97.323534, "vol_target": null}, "0.0075": {"annual_turnover": 2.470509, "avg_slot_utilization": 0.540284, "cagr": -0.052123, "confirm_days": null, "cumulative_return": -0.043628, "daily_sharpe": -0.433325, "empty_day_ratio": 0.407583, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 211, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 0.0, "exposure_fallback_days": 0, "max_drawdown": 0.11815, "max_entry_premium": null, "max_single_name_weight": 0.193418, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 18, "risk_budget_hit_rate": 0.6, "risk_budget_trade_count": 30, "risk_per_trade": 0.0075, "sample_days": 210, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 95.637182, "vol_target": null}, "0.01": {"annual_turnover": 3.106649, "avg_slot_utilization": 0.540284, "cagr": -0.117376, "confirm_days": null, "cumulative_return": -0.098817, "daily_sharpe": -0.852471, "empty_day_ratio": 0.407583, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 211, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 1, "exposure_fallback_day_ratio": 0.0, "exposure_fallback_days": 0, "max_drawdown": 0.154783, "max_entry_premium": null, "max_single_name_weight": 0.257561, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 18, "risk_budget_hit_rate": 0.6, "risk_budget_trade_count": 30, "risk_per_trade": 0.01, "sample_days": 210, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 90.118286, "vol_target": null}}, "train_rows": 529}

## Single-Name Cap Sensitivity

| single_name_cap | diagnostic_no_cap | cumulative_return | max_drawdown | daily_sharpe | max_single_name_weight |
|---:|---|---:|---:|---:|---:|
| 0.100000 | False | 0.104144 | 0.141348 | 0.844943 | 0.147920 |
| 0.150000 | False | 0.106070 | 0.144072 | 0.843448 | 0.154808 |
| 0.200000 | False | 0.106070 | 0.144072 | 0.843448 | 0.154808 |
| NA | True | 0.106070 | 0.144072 | 0.843448 | 0.154808 |

## Slices

| slice_type | slice_value | row_count | fixed_20d_return | risk_0p005_return | increment | risk_0p005_max_drawdown | risk_0p005_sharpe |
|---|---|---:|---:|---:|---:|---:|---:|
| calendar_year | 2024 | 253 | -0.153840 | -0.047253 | 0.106587 | 0.050863 | -3.173879 |
| calendar_year | 2025 | 529 | -0.165938 | 0.069171 | 0.235109 | 0.144072 | 0.690396 |
| calendar_year | 2026 | 44 | 0.301043 | 0.085820 | -0.215223 | 0.018738 | 1.835687 |
| calendar_half | 2024-H2 | 253 | -0.153840 | -0.047253 | 0.106587 | 0.050863 | -3.173879 |
| calendar_half | 2025-H1 | 265 | -0.090206 | 0.036274 | 0.126480 | 0.074727 | 0.698223 |
| calendar_half | 2025-H2 | 264 | -0.042330 | 0.068161 | 0.110491 | 0.090521 | 0.796019 |
| calendar_half | 2026-H1 | 44 | 0.301043 | 0.085820 | -0.215223 | 0.018738 | 1.835687 |
| market_state | WARM | 291 | 0.027734 | 0.093505 | 0.065771 | 0.084404 | 1.031876 |
| market_state | HOT | 342 | 0.269359 | 0.124633 | -0.144726 | 0.085464 | 1.014147 |
| market_state | OVERHEAT | 193 | -0.217782 | -0.050283 | 0.167499 | 0.055964 | -0.786347 |
| signal_kind | stock_candidate | 826 | -0.081789 | 0.106070 | 0.187859 | 0.144072 | 0.843448 |
| liquidity_bucket | <20m | 826 | -0.081789 | 0.106070 | 0.187859 | 0.144072 | 0.843448 |
| entry_premium_bucket | [2%,3%) | 62 | -0.019257 | -0.013878 | 0.005379 | 0.055007 | -0.210556 |
| entry_premium_bucket | [1%,2%) | 86 | 0.016641 | -0.016075 | -0.032716 | 0.054827 | -0.180223 |
| entry_premium_bucket | >=5% | 143 | -0.238470 | -0.028106 | 0.210364 | 0.082370 | -0.541164 |
| entry_premium_bucket | [3%,5%) | 87 | -0.146008 | -0.024040 | 0.121968 | 0.069715 | -0.357948 |
| entry_premium_bucket | <0 | 303 | -0.246922 | 0.068785 | 0.315707 | 0.100320 | 0.483946 |
| entry_premium_bucket | [0,1%) | 145 | 0.118520 | 0.119010 | 0.000490 | 0.073868 | 0.999197 |
| volatility_regime | UNKNOWN | 53 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | NA |
| volatility_regime | high_vol | 321 | 0.139638 | 0.055600 | -0.084038 | 0.077779 | 0.633802 |
| volatility_regime | mid_vol | 185 | -0.276033 | -0.049550 | 0.226483 | 0.119496 | -0.396528 |
| volatility_regime | low_vol | 267 | 0.353978 | 0.141906 | -0.212072 | 0.066481 | 1.146746 |

## Top Contributions

{"fixed_20d_equal": {"largest_5_pnl_dates": [{"date": "2025-03-06", "pnl": 8.912146}, {"date": "2026-01-30", "pnl": 8.105509}, {"date": "2025-04-03", "pnl": -7.282936}, {"date": "2025-01-23", "pnl": -7.253564}, {"date": "2025-01-21", "pnl": -6.843725}], "top_10_symbols_by_pnl": [{"pnl": 8.105509, "stock_code": "300058.SZ"}, {"pnl": 5.874089, "stock_code": "688143.SH"}, {"pnl": 4.88571, "stock_code": "002126.SZ"}, {"pnl": 4.61463, "stock_code": "300780.SZ"}, {"pnl": 4.333996, "stock_code": "603989.SH"}, {"pnl": 4.170672, "stock_code": "600888.SH"}, {"pnl": 3.708923, "stock_code": "000887.SZ"}, {"pnl": 3.639843, "stock_code": "688001.SH"}, {"pnl": 3.182991, "stock_code": "001311.SZ"}, {"pnl": 2.987875, "stock_code": "003033.SZ"}]}, "risk_budget_rpt_0p005": {"largest_5_pnl_dates": [{"date": "2025-03-06", "pnl": 8.76871}, {"date": "2026-01-26", "pnl": 5.355889}, {"date": "2026-01-28", "pnl": 3.561111}, {"date": "2025-01-23", "pnl": -3.139166}, {"date": "2026-01-30", "pnl": 2.284199}], "top_10_symbols_by_pnl": [{"pnl": 5.355889, "stock_code": "300780.SZ"}, {"pnl": 3.670165, "stock_code": "000887.SZ"}, {"pnl": 3.561111, "stock_code": "001311.SZ"}, {"pnl": 3.270623, "stock_code": "003033.SZ"}, {"pnl": 2.61402, "stock_code": "002126.SZ"}, {"pnl": 2.284199, "stock_code": "300058.SZ"}, {"pnl": 1.718921, "stock_code": "600360.SH"}, {"pnl": 1.479417, "stock_code": "603989.SH"}, {"pnl": 1.385452, "stock_code": "301191.SZ"}, {"pnl": 1.193172, "stock_code": "600888.SH"}]}, "risk_budget_rpt_0p01": {"largest_5_pnl_dates": [{"date": "2025-03-06", "pnl": 12.520905}, {"date": "2026-01-26", "pnl": 9.249227}, {"date": "2025-01-23", "pnl": -6.235178}, {"date": "2026-01-28", "pnl": 6.156172}, {"date": "2026-01-30", "pnl": 3.94035}], "top_10_symbols_by_pnl": [{"pnl": 9.249227, "stock_code": "300780.SZ"}, {"pnl": 6.979958, "stock_code": "000887.SZ"}, {"pnl": 6.220104, "stock_code": "003033.SZ"}, {"pnl": 6.156172, "stock_code": "001311.SZ"}, {"pnl": 3.94035, "stock_code": "300058.SZ"}, {"pnl": 3.376414, "stock_code": "600360.SH"}, {"pnl": 2.9482, "stock_code": "603989.SH"}, {"pnl": 2.655721, "stock_code": "301191.SZ"}, {"pnl": 2.43538, "stock_code": "600888.SH"}, {"pnl": 2.066586, "stock_code": "688143.SH"}]}}

## Recommendation

{"criteria": {"beats_fixed_20d": true, "bootstrap_not_dominated_by_few_dates": false, "daily_sharpe_above_0p8": true, "fallback_ratio_below_10pct": true, "liquidity_not_eliminating_all_trades": false, "max_drawdown_below_25pct": true, "max_single_name_weight_lte_20pct": true}, "reason": "fallback/liquidity/robustness gates must all pass before paper trading.", "risk_budget_0p005": "research_only", "risk_budget_0p010_too_concentrated": true, "selected_walk_forward_risk_per_trade": 0.003, "status": "research_only"}

## Output CSV

- fixed_20d_equal: docs\pnl\batch3_equity_fixed_20d_equal.csv
- fixed_5d_equal: docs\pnl\batch3_equity_fixed_5d_equal.csv
- risk_budget_rpt_0p003: docs\pnl\batch3_equity_risk_budget_rpt_0p003.csv
- risk_budget_rpt_0p005: docs\pnl\batch3_equity_risk_budget_rpt_0p005.csv
- risk_budget_rpt_0p0075: docs\pnl\batch3_equity_risk_budget_rpt_0p0075.csv
- risk_budget_rpt_0p01: docs\pnl\batch3_equity_risk_budget_rpt_0p01.csv
- vol_target_0p15_control: docs\pnl\batch3_equity_vol_target_0p15_control.csv
- vol_target_0p2_control: docs\pnl\batch3_equity_vol_target_0p2_control.csv
- fixed_20d_exposure_matched_to_risk_0p005: docs\pnl\batch3_equity_fixed_20d_exposure_matched_to_risk_0p005.csv
