# 2026-07 Portfolio Backtest Report

- status: ready
- db_path: data\moss.duckdb
- signal_kind: stock_candidate
- portfolio_engine_version: pbt_v2_path_mode
- mode: path
- execution_row_count: 826
- metric_basis: T+1 open execution history, net adjusted horizon returns, daily market_gate exposure when available; otherwise policy state fallback; risk_budget variants size by risk_per_trade / stop_distance_pct with policy caps; max_entry_premium variants skip rows with entry_price/signal_close - 1 above the threshold; probe_pyramid variants use half-size probes, close>signal-high confirmation, and next-open add/failed-exit path accounting
- exposure_basis: per_date_actual
- daily_exposure_rows: 113
- price_path_count: 811
- price_path_adj_factor_missing_rows: 3564
- benchmark_tables: ['fact_choice_macro_daily']
- issues: ['Daily exposure source counts: missing=524, replayed=113', '524 dates lacked persisted or replayed gate exposure; portfolio uses state fallback for those dates.']

## Strategy Metrics

| variant | sizing | entry_style | risk_per_trade | max_entry_premium | vol_target | entry_premium_blocked | probe_confirm_rate | probe_failed_exit | probe_failed_avg_loss | probe_confirmed_avg_return | probe_confirmed_median_return | probe_confirmed_win_rate | terminal_value | cumulative_return | cagr | max_drawdown | daily_sharpe | annual_turnover | avg_slot_utilization | empty_day_ratio | max_single_name_weight | risk_budget_hit_rate | stop_ref_fallback | exposure_cap_clipped | exposure_fallback_days | exposure_fallback_day_ratio | skips |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_5d | equal_weight | full | NA | NA | NA | 0 | NA | 0 | NA | NA | NA | NA | 98.605138 | -0.013949 | -0.011281 | 0.482892 | 0.181213 | 35.801535 | 0.608307 | 0.099042 | 0.291966 | NA | 0 | 0 | 253 | 0.808307 | 590 |
| fixed_20d | equal_weight | full | NA | NA | NA | 0 | NA | 0 | NA | NA | NA | NA | 102.303643 | 0.023036 | 0.015178 | 0.535223 | 0.231141 | 7.526060 | 0.756545 | 0.115183 | 0.297550 | NA | 0 | 0 | 296 | 0.774869 | 750 |
| fixed_20d_risk_budget_rpt_0p005 | risk_budget | full | 0.005000 | NA | NA | 0 | NA | 0 | NA | NA | NA | NA | 119.335856 | 0.193359 | 0.124029 | 0.144072 | 1.141817 | 2.598875 | 0.756545 | 0.123037 | 0.160890 | 0.710526 | 0 | 0 | 296 | 0.774869 | 750 |
| fixed_20d_risk_budget_rpt_0p010 | risk_budget | full | 0.010000 | NA | NA | 0 | NA | 0 | NA | NA | NA | NA | 138.079430 | 0.380794 | 0.237895 | 0.268024 | 1.123632 | 5.286961 | 0.756545 | 0.123037 | 0.302862 | 0.710526 | 0 | 0 | 296 | 0.774869 | 750 |
| fixed_20d_max_entry_premium_0p02 | equal_weight | full | NA | 0.020000 | NA | 252 | NA | 0 | NA | NA | NA | NA | 96.197442 | -0.038026 | -0.025315 | 0.509271 | 0.089231 | 7.234877 | 0.697906 | 0.109948 | 0.286873 | NA | 0 | 0 | 296 | 0.774869 | 756 |
| fixed_20d_max_entry_premium_0p03 | equal_weight | full | NA | 0.030000 | NA | 190 | NA | 0 | NA | NA | NA | NA | 91.889544 | -0.081105 | -0.054408 | 0.526560 | 0.016171 | 7.219243 | 0.747120 | 0.107330 | 0.233541 | NA | 0 | 0 | 296 | 0.774869 | 751 |
| fixed_20d_max_entry_premium_none | equal_weight | full | NA | NA | NA | 0 | NA | 0 | NA | NA | NA | NA | 102.303643 | 0.023036 | 0.015178 | 0.535223 | 0.231141 | 7.526060 | 0.756545 | 0.115183 | 0.297550 | NA | 0 | 0 | 296 | 0.774869 | 750 |
| fixed_20d_vol_target_0p15 | equal_weight | full | NA | NA | 0.150000 | 0 | NA | 0 | NA | NA | NA | NA | 95.334135 | -0.046659 | -0.031110 | 0.535223 | 0.088721 | 7.407941 | 0.756545 | 0.115183 | 0.297550 | NA | 0 | 0 | 296 | 0.774869 | 750 |
| fixed_20d_vol_target_0p20 | equal_weight | full | NA | NA | 0.200000 | 0 | NA | 0 | NA | NA | NA | NA | 100.250993 | 0.002510 | 0.001659 | 0.535223 | 0.190538 | 7.491138 | 0.756545 | 0.115183 | 0.297550 | NA | 0 | 0 | 296 | 0.774869 | 750 |
| fixed_20d_probe_pyramid_cd_3 | equal_weight | probe_pyramid | NA | NA | NA | 0 | 0.122951 | 214 | 0.044051 | 0.028988 | 0.003160 | 0.500000 | 85.635890 | -0.143641 | -0.097479 | 0.398082 | -0.294612 | 14.149133 | 0.637696 | 0.225131 | 0.258483 | NA | 0 | 0 | 296 | 0.774869 | 582 |
| fixed_20d_probe_pyramid_cd_5 | equal_weight | probe_pyramid | NA | NA | NA | 0 | 0.115183 | 169 | 0.057507 | 0.059257 | -0.014954 | 0.454545 | 81.649953 | -0.183500 | -0.125487 | 0.442865 | -0.477397 | 10.233743 | 0.661257 | 0.217277 | 0.274479 | NA | 0 | 0 | 296 | 0.774869 | 635 |

## Benchmark Comparison

| variant | benchmark_status | strategy_return | csi300_buy_hold_return | gate_timing_return | stock_selection_increment |
|---|---|---:|---:|---:|---:|
| fixed_5d | ready | -0.013949 | 0.099780 | 0.086555 | -0.100503 |
| fixed_20d | ready | 0.023036 | 0.068541 | 0.071497 | -0.048461 |
| fixed_20d_risk_budget_rpt_0p005 | ready | 0.193359 | 0.068541 | 0.071497 | 0.121862 |
| fixed_20d_risk_budget_rpt_0p010 | ready | 0.380794 | 0.068541 | 0.071497 | 0.309297 |
| fixed_20d_max_entry_premium_0p02 | ready | -0.038026 | 0.068541 | 0.071497 | -0.109523 |
| fixed_20d_max_entry_premium_0p03 | ready | -0.081105 | 0.068541 | 0.071497 | -0.152602 |
| fixed_20d_max_entry_premium_none | ready | 0.023036 | 0.068541 | 0.071497 | -0.048461 |
| fixed_20d_vol_target_0p15 | ready | -0.046659 | 0.068541 | 0.071497 | -0.118156 |
| fixed_20d_vol_target_0p20 | ready | 0.002510 | 0.068541 | 0.071497 | -0.068987 |
| fixed_20d_probe_pyramid_cd_3 | ready | -0.143641 | 0.068541 | 0.071497 | -0.215138 |
| fixed_20d_probe_pyramid_cd_5 | ready | -0.183500 | 0.068541 | 0.071497 | -0.254998 |

## Vol Target

- status: ready
- window: 20

| target_vol | line | cumulative_return | cagr | max_drawdown | daily_sharpe | avg_exposure | avg_multiplier | insufficient_history_days |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0.150000 | gate_index | 0.071497 | 0.168099 | 0.049837 | 1.667791 | 0.373894 | NA | NA |
| 0.150000 | gate_voltarget_index | 0.050294 | 0.116732 | 0.046874 | 1.383963 | 0.322743 | 0.911920 | 19 |
| 0.200000 | gate_index | 0.071497 | 0.168099 | 0.049837 | 1.667791 | 0.373894 | NA | NA |
| 0.200000 | gate_voltarget_index | 0.066996 | 0.157088 | 0.049837 | 1.603779 | 0.365952 | 0.987510 | 19 |

## Liquidity Floor Observation

- min_daily_amount: 200000000.0
- known_pass_rows: 0
- known_fail_rows: 826
- missing_amount_rows: 0
- filtered_row_count: 0

| variant | before_cumulative_return | after_floor_cumulative_return | before_max_drawdown | after_floor_max_drawdown |
|---|---:|---:|---:|---:|
| fixed_5d | -0.013949 | 0.000000 | 0.482892 | 0.000000 |
| fixed_20d | 0.023036 | 0.000000 | 0.535223 | 0.000000 |
| fixed_20d_risk_budget_rpt_0p005 | 0.193359 | 0.000000 | 0.144072 | 0.000000 |
| fixed_20d_risk_budget_rpt_0p010 | 0.380794 | 0.000000 | 0.268024 | 0.000000 |
| fixed_20d_max_entry_premium_0p02 | -0.038026 | 0.000000 | 0.509271 | 0.000000 |
| fixed_20d_max_entry_premium_0p03 | -0.081105 | 0.000000 | 0.526560 | 0.000000 |
| fixed_20d_max_entry_premium_none | 0.023036 | 0.000000 | 0.535223 | 0.000000 |
| fixed_20d_vol_target_0p15 | -0.046659 | 0.000000 | 0.535223 | 0.000000 |
| fixed_20d_vol_target_0p20 | 0.002510 | 0.000000 | 0.535223 | 0.000000 |
| fixed_20d_probe_pyramid_cd_3 | -0.143641 | 0.000000 | 0.398082 | 0.000000 |
| fixed_20d_probe_pyramid_cd_5 | -0.183500 | 0.000000 | 0.442865 | 0.000000 |

## Variant Notes

- risk_exit_variant: not_run - Task5 report did not provide per-position risk-exit dates in the local dataset.
- live candidate behavior: unchanged; daily_amount/liquidity_floor_pass are observation fields only.
- hold_progress_matrix: ready (2026-07-batch2-hold-progress-matrix.md)

## Output Files

- fixed_5d: docs\pnl\portfolio_equity_fixed_5d.csv
- fixed_20d: docs\pnl\portfolio_equity_fixed_20d.csv
- fixed_20d_risk_budget_rpt_0p005: docs\pnl\portfolio_equity_fixed_20d_risk_budget_rpt_0p005.csv
- fixed_20d_risk_budget_rpt_0p010: docs\pnl\portfolio_equity_fixed_20d_risk_budget_rpt_0p010.csv
- fixed_20d_max_entry_premium_0p02: docs\pnl\portfolio_equity_fixed_20d_max_entry_premium_0p02.csv
- fixed_20d_max_entry_premium_0p03: docs\pnl\portfolio_equity_fixed_20d_max_entry_premium_0p03.csv
- fixed_20d_max_entry_premium_none: docs\pnl\portfolio_equity_fixed_20d_max_entry_premium_none.csv
- fixed_20d_vol_target_0p15: docs\pnl\portfolio_equity_fixed_20d_vol_target_0p15.csv
- fixed_20d_vol_target_0p20: docs\pnl\portfolio_equity_fixed_20d_vol_target_0p20.csv
- fixed_20d_probe_pyramid_cd_3: docs\pnl\portfolio_equity_fixed_20d_probe_pyramid_cd_3.csv
- fixed_20d_probe_pyramid_cd_5: docs\pnl\portfolio_equity_fixed_20d_probe_pyramid_cd_5.csv
