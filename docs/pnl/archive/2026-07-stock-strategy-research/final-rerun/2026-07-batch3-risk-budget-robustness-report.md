# 2026-07 Batch 3 Risk-Budget Robustness Report

- status: research_only
- signal_kind: stock_candidate
- execution_row_count: 826
- recommendation: research_only

## Variant Metrics

| variant | cumulative_return | cagr | max_drawdown | daily_sharpe | sortino | calmar | annual_turnover | avg_exposure | max_single_name_weight | avg_position_count | win_rate | avg_winner | avg_loser | fallback_exposure_ratio | missing_adjusted_path_ratio | liq_200m_pass | liq_200m_fail |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_20d_equal | 0.023036 | 0.015178 | 0.535223 | 0.231141 | 0.402412 | 0.028358 | 7.526060 | 0.614772 | 0.297550 | 3.782723 | 0.407895 | 0.263681 | -0.130122 | 0.774869 | 0.175922 | 0 | 826 |
| fixed_5d_equal | -0.013949 | -0.011281 | 0.482892 | 0.181213 | 0.329180 | -0.023361 | 35.801535 | 0.506131 | 0.291966 | 3.041534 | 0.389831 | 0.142645 | -0.080303 | 0.808307 | 0.175922 | 0 | 826 |
| risk_budget_rpt_0p003 | 0.116756 | 0.075773 | 0.088748 | 1.153583 | 2.299589 | 0.853800 | 1.541025 | 0.116057 | 0.099008 | 3.782723 | 0.407895 | 0.264818 | -0.125258 | 0.774869 | 0.175922 | 0 | 826 |
| risk_budget_rpt_0p005 | 0.193359 | 0.124029 | 0.144072 | 1.141817 | 2.268681 | 0.860882 | 2.598875 | 0.192805 | 0.160890 | 3.782723 | 0.407895 | 0.264818 | -0.125258 | 0.774869 | 0.175922 | 0 | 826 |
| risk_budget_rpt_0p0075 | 0.286716 | 0.181445 | 0.209149 | 1.127016 | 2.230126 | 0.867539 | 3.947142 | 0.288164 | 0.234026 | 3.782723 | 0.407895 | 0.264818 | -0.125258 | 0.774869 | 0.175922 | 0 | 826 |
| risk_budget_rpt_0p01 | 0.380794 | 0.237895 | 0.268024 | 1.123632 | 2.221065 | 0.887588 | 5.286961 | 0.380532 | 0.302862 | 3.782723 | 0.407895 | 0.264818 | -0.125258 | 0.774869 | 0.175922 | 0 | 826 |
| vol_target_0p15_control | -0.046659 | -0.031110 | 0.535223 | 0.088721 | 0.153040 | -0.058125 | 7.407941 | 0.605376 | 0.297550 | 3.782723 | 0.407895 | 0.263681 | -0.130122 | 0.774869 | 0.175922 | 0 | 826 |
| vol_target_0p2_control | 0.002510 | 0.001659 | 0.535223 | 0.190538 | 0.330659 | 0.003100 | 7.491138 | 0.612019 | 0.297550 | 3.782723 | 0.407895 | 0.263681 | -0.130122 | 0.774869 | 0.175922 | 0 | 826 |
| fixed_20d_exposure_matched_to_risk_0p005 | 0.061574 | 0.040313 | 0.149745 | 0.527460 | 0.939289 | 0.269211 | 2.022308 | 0.156235 | 0.071700 | 3.981675 | 0.425000 | 0.221667 | -0.125902 | 0.000000 | 0.175922 | 0 | 826 |

## Bootstrap By Trade Date

{"date_count": 381, "iterations": 300, "mean_increment": 0.076779, "p10_increment": -0.27736, "p50_increment": 0.035785, "p90_increment": 0.491997, "status": "ready"}

## Walk Forward

{"selected_risk_per_trade": 0.003, "split_date": "2025-07-14", "status": "ready", "test_fixed_20d_metrics": {"annual_turnover": 3.736044, "avg_slot_utilization": 0.324084, "cagr": 0.362812, "confirm_days": null, "cumulative_return": 0.596813, "daily_sharpe": 1.690984, "empty_day_ratio": 0.554974, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 86, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 0.774869, "exposure_fallback_days": 296, "max_drawdown": 0.154705, "max_entry_premium": null, "max_single_name_weight": 0.301305, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 0, "risk_budget_hit_rate": null, "risk_budget_trade_count": 0, "risk_per_trade": null, "sample_days": 381, "single_name_cap": null, "sizing": "equal_weight", "stop_ref_fallback": 0, "terminal_value": 159.681342, "vol_target": null}, "test_rows": 297, "test_selected_metrics": {"annual_turnover": 0.768252, "avg_slot_utilization": 0.331414, "cagr": 0.114826, "confirm_days": null, "cumulative_return": 0.178617, "daily_sharpe": 2.473964, "empty_day_ratio": 0.552356, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 86, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 0.774869, "exposure_fallback_days": 296, "max_drawdown": 0.026885, "max_entry_premium": null, "max_single_name_weight": 0.099008, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 24, "risk_budget_hit_rate": 0.727273, "risk_budget_trade_count": 33, "risk_per_trade": 0.003, "sample_days": 381, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 117.861654, "vol_target": null}, "train_metrics_by_risk": {"0.003": {"annual_turnover": 1.558514, "avg_slot_utilization": 0.810427, "cagr": 0.016361, "confirm_days": null, "cumulative_return": 0.013616, "daily_sharpe": 0.30138, "empty_day_ratio": 0.127962, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 0, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 1.0, "exposure_fallback_days": 211, "max_drawdown": 0.059639, "max_entry_premium": null, "max_single_name_weight": 0.082405, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 30, "risk_budget_hit_rate": 0.666667, "risk_budget_trade_count": 45, "risk_per_trade": 0.003, "sample_days": 210, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 101.361564, "vol_target": null}, "0.005": {"annual_turnover": 2.636329, "avg_slot_utilization": 0.810427, "cagr": 0.023806, "confirm_days": null, "cumulative_return": 0.019799, "daily_sharpe": 0.297219, "empty_day_ratio": 0.127962, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 0, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 1.0, "exposure_fallback_days": 211, "max_drawdown": 0.096691, "max_entry_premium": null, "max_single_name_weight": 0.133479, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 30, "risk_budget_hit_rate": 0.666667, "risk_budget_trade_count": 45, "risk_per_trade": 0.005, "sample_days": 210, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 101.97991, "vol_target": null}, "0.0075": {"annual_turnover": 4.022589, "avg_slot_utilization": 0.810427, "cagr": 0.029292, "confirm_days": null, "cumulative_return": 0.024351, "daily_sharpe": 0.291403, "empty_day_ratio": 0.127962, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 0, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 1.0, "exposure_fallback_days": 211, "max_drawdown": 0.140351, "max_entry_premium": null, "max_single_name_weight": 0.193418, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 30, "risk_budget_hit_rate": 0.666667, "risk_budget_trade_count": 45, "risk_per_trade": 0.0075, "sample_days": 210, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 102.435132, "vol_target": null}, "0.01": {"annual_turnover": 5.447241, "avg_slot_utilization": 0.810427, "cagr": 0.030641, "confirm_days": null, "cumulative_return": 0.025469, "daily_sharpe": 0.284984, "empty_day_ratio": 0.127962, "entry_premium_blocked": 0, "entry_style": "full", "exposure_actual_days": 0, "exposure_basis": "per_date_actual", "exposure_cap_clipped": 0, "exposure_fallback_day_ratio": 1.0, "exposure_fallback_days": 211, "max_drawdown": 0.181398, "max_entry_premium": null, "max_single_name_weight": 0.249419, "mode": "path", "portfolio_engine_version": "pbt_v2_path_mode", "probe_confirm_rate": null, "probe_confirmed": 0, "probe_confirmed_avg_return": null, "probe_confirmed_median_return": null, "probe_confirmed_win_rate": null, "probe_entries": 0, "probe_failed_avg_loss": null, "probe_failed_avg_return": null, "probe_failed_exit": 0, "probe_fraction": null, "risk_budget_hit_count": 30, "risk_budget_hit_rate": 0.666667, "risk_budget_trade_count": 45, "risk_per_trade": 0.01, "sample_days": 210, "single_name_cap": 0.25, "sizing": "risk_budget", "stop_ref_fallback": 0, "terminal_value": 102.546948, "vol_target": null}}, "train_rows": 529}

## Single-Name Cap Sensitivity

| single_name_cap | diagnostic_no_cap | cumulative_return | max_drawdown | daily_sharpe | max_single_name_weight |
|---:|---|---:|---:|---:|---:|
| 0.100000 | False | 0.193986 | 0.141348 | 1.152037 | 0.153710 |
| 0.150000 | False | 0.193359 | 0.144072 | 1.141817 | 0.160890 |
| 0.200000 | False | 0.193359 | 0.144072 | 1.141817 | 0.160890 |
| NA | True | 0.193359 | 0.144072 | 1.141817 | 0.160890 |

## Slices

| slice_type | slice_value | row_count | fixed_20d_return | risk_0p005_return | increment | risk_0p005_max_drawdown | risk_0p005_sharpe |
|---|---|---:|---:|---:|---:|---:|---:|
| calendar_year | 2024 | 253 | -0.055995 | -0.001670 | 0.054325 | 0.095855 | 0.118668 |
| calendar_year | 2025 | 529 | -0.282934 | 0.007819 | 0.290753 | 0.144072 | 0.118697 |
| calendar_year | 2026 | 44 | 0.511324 | 0.186080 | -0.325244 | 0.020158 | 2.494928 |
| calendar_half | 2024-H2 | 253 | -0.055995 | -0.001670 | 0.054325 | 0.095855 | 0.118668 |
| calendar_half | 2025-H1 | 265 | -0.075540 | 0.036274 | 0.111814 | 0.074727 | 0.698223 |
| calendar_half | 2025-H2 | 264 | -0.238185 | 0.006867 | 0.245052 | 0.090521 | 0.117714 |
| calendar_half | 2026-H1 | 44 | 0.511324 | 0.186080 | -0.325244 | 0.020158 | 2.494928 |
| market_state | WARM | 291 | 0.356551 | 0.246724 | -0.109827 | 0.084404 | 1.747512 |
| market_state | HOT | 342 | -0.038234 | 0.064776 | 0.103010 | 0.127447 | 0.533304 |
| market_state | OVERHEAT | 193 | -0.384514 | -0.128157 | 0.256357 | 0.145726 | -1.532290 |
| signal_kind | stock_candidate | 826 | 0.023036 | 0.193359 | 0.170323 | 0.144072 | 1.141817 |
| liquidity_bucket | <20m | 826 | 0.023036 | 0.193359 | 0.170323 | 0.144072 | 1.141817 |
| entry_premium_bucket | [2%,3%) | 62 | 0.088934 | 0.021351 | -0.067583 | 0.082922 | 0.296627 |
| entry_premium_bucket | [1%,2%) | 86 | -0.200984 | -0.039530 | 0.161454 | 0.095665 | -0.409188 |
| entry_premium_bucket | >=5% | 143 | -0.324616 | -0.051881 | 0.272735 | 0.111421 | -0.783900 |
| entry_premium_bucket | [3%,5%) | 87 | -0.017643 | 0.004524 | 0.022167 | 0.055743 | 0.083809 |
| entry_premium_bucket | <0 | 303 | 0.008922 | 0.138242 | 0.129320 | 0.100320 | 0.845506 |
| entry_premium_bucket | [0,1%) | 145 | 0.271471 | 0.146324 | -0.125147 | 0.073868 | 1.091998 |
| volatility_regime | UNKNOWN | 782 | -0.323086 | 0.006136 | 0.329222 | 0.144072 | 0.126839 |
| volatility_regime | low_vol | 13 | 0.137966 | 0.023752 | -0.114214 | 0.012800 | 1.017559 |
| volatility_regime | mid_vol | 19 | 0.106590 | 0.018322 | -0.088268 | 0.039655 | 0.389073 |
| volatility_regime | high_vol | 12 | 0.267078 | 0.144725 | -0.122353 | 0.010669 | 2.294665 |

## Top Contributions

{"fixed_20d_equal": {"largest_5_pnl_dates": [{"date": "2025-03-06", "pnl": 14.914042}, {"date": "2024-10-29", "pnl": 13.595775}, {"date": "2024-12-25", "pnl": -10.756242}, {"date": "2026-05-11", "pnl": 10.54036}, {"date": "2025-04-03", "pnl": -8.512205}], "top_10_symbols_by_pnl": [{"pnl": 8.175998, "stock_code": "002126.SZ"}, {"pnl": 6.770238, "stock_code": "688143.SH"}, {"pnl": 6.206701, "stock_code": "000887.SZ"}, {"pnl": 6.128219, "stock_code": "688693.SH"}, {"pnl": 5.268833, "stock_code": "300780.SZ"}, {"pnl": 5.104245, "stock_code": "300968.SZ"}, {"pnl": 5.000062, "stock_code": "003033.SZ"}, {"pnl": 4.950707, "stock_code": "603989.SH"}, {"pnl": 4.500275, "stock_code": "600888.SH"}, {"pnl": 4.412141, "stock_code": "300571.SZ"}]}, "risk_budget_rpt_0p005": {"largest_5_pnl_dates": [{"date": "2025-03-06", "pnl": 9.188242}, {"date": "2026-05-11", "pnl": 8.20221}, {"date": "2024-10-29", "pnl": 5.793438}, {"date": "2026-01-26", "pnl": 5.612138}, {"date": "2025-01-23", "pnl": -3.301517}], "top_10_symbols_by_pnl": [{"pnl": 5.612138, "stock_code": "300780.SZ"}, {"pnl": 5.461555, "stock_code": "300571.SZ"}, {"pnl": 3.845762, "stock_code": "000887.SZ"}, {"pnl": 3.427104, "stock_code": "003033.SZ"}, {"pnl": 3.202861, "stock_code": "688485.SH"}, {"pnl": 2.740655, "stock_code": "688693.SH"}, {"pnl": 2.739085, "stock_code": "002126.SZ"}, {"pnl": 1.713356, "stock_code": "600360.SH"}, {"pnl": 1.598674, "stock_code": "603989.SH"}, {"pnl": 1.567662, "stock_code": "600030.SH"}]}, "risk_budget_rpt_0p01": {"largest_5_pnl_dates": [{"date": "2025-03-06", "pnl": 18.241253}, {"date": "2026-05-11", "pnl": 16.392218}, {"date": "2024-10-29", "pnl": 11.586876}, {"date": "2026-01-26", "pnl": 10.524834}, {"date": "2025-01-23", "pnl": -6.872544}], "top_10_symbols_by_pnl": [{"pnl": 10.914985, "stock_code": "300571.SZ"}, {"pnl": 10.524834, "stock_code": "300780.SZ"}, {"pnl": 7.634922, "stock_code": "000887.SZ"}, {"pnl": 6.803767, "stock_code": "003033.SZ"}, {"pnl": 6.341588, "stock_code": "688485.SH"}, {"pnl": 5.477233, "stock_code": "688693.SH"}, {"pnl": 5.437857, "stock_code": "002126.SZ"}, {"pnl": 3.561464, "stock_code": "603989.SH"}, {"pnl": 3.510769, "stock_code": "600360.SH"}, {"pnl": 3.135325, "stock_code": "600030.SH"}]}}

## Recommendation

{"criteria": {"beats_fixed_20d": true, "bootstrap_not_dominated_by_few_dates": false, "daily_sharpe_above_0p8": true, "fallback_ratio_below_10pct": false, "liquidity_not_eliminating_all_trades": false, "max_drawdown_below_25pct": true, "max_single_name_weight_lte_20pct": true}, "reason": "fallback/liquidity/robustness gates must all pass before paper trading.", "risk_budget_0p005": "research_only", "risk_budget_0p010_too_concentrated": true, "selected_walk_forward_risk_per_trade": 0.003, "status": "research_only"}

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
