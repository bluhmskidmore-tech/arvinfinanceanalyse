# 2026-07 Batch 3 Hold-Progress Exit Path-Mode Report

- status: research_only
- engine_mode: path_mode_report_layer_v1
- position_level_csv: docs\pnl\batch3_hold_progress_exit_path_mode_positions.csv
- portfolio_level_csv: docs\pnl\batch3_hold_progress_exit_path_mode_portfolio.csv
- recommendation: research_only

This simulation exits on the day-k trigger's next tradable open and does not use future path data to decide the trigger. It remains report-layer only.

## Rule Summary

| rule | fixed_20d_return_delta | fixed_20d_mdd_delta | risk_0p005_return_delta | risk_0p005_mdd_delta | risk_0p010_return_delta | risk_0p010_mdd_delta |
|---|---:|---:|---:|---:|---:|---:|
| day3_underwater_exit | 0.015234 | -0.063685 | 0.019668 | -0.051680 | 0.074598 | -0.101356 |
| day3_underwater_reduce_half | 0.108663 | -0.089189 | 0.008443 | -0.019396 | 0.020152 | -0.034215 |
| day5_no_progress_reduce_half | -0.077678 | 0.020682 | -0.078141 | 0.004059 | -0.126853 | 0.006752 |
| day5_underwater_exit | 0.252550 | -0.037793 | 0.102921 | -0.031776 | 0.218430 | -0.054877 |
| day5_underwater_reduce_half | 0.081064 | -0.057424 | 0.017580 | -0.013305 | 0.039966 | -0.024296 |
| day8_stagnation_exit | -0.069418 | 0.062382 | -0.099890 | 0.062635 | -0.194593 | 0.107799 |
| day8_stagnation_exit_lt0 | -0.069418 | 0.062382 | -0.099890 | 0.062635 | -0.194593 | 0.107799 |
| day8_stagnation_exit_lt2 | -0.301614 | 0.185928 | -0.116996 | 0.071517 | -0.219363 | 0.116955 |

## Portfolio Comparison

| base_variant | rule | cumulative_return | cagr | max_drawdown | daily_sharpe | return_delta_vs_baseline | max_drawdown_delta_vs_baseline | exposure_fallback_day_ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| fixed_20d | baseline | -0.081789 | -0.054874 | 0.457000 | -0.103494 | 0.000000 | 0.000000 | 0.000000 |
| fixed_20d | day3_underwater_exit | -0.066555 | -0.044532 | 0.393315 | -0.028936 | 0.015234 | -0.063685 | 0.000000 |
| fixed_20d | day3_underwater_reduce_half | 0.026874 | 0.017695 | 0.367811 | 0.187661 | 0.108663 | -0.089189 | 0.000000 |
| fixed_20d | day5_no_progress_reduce_half | -0.159467 | -0.108545 | 0.477682 | -0.360539 | -0.077678 | 0.020682 | 0.000000 |
| fixed_20d | day5_underwater_exit | 0.170761 | 0.109906 | 0.419207 | 0.515672 | 0.252550 | -0.037793 | 0.000000 |
| fixed_20d | day5_underwater_reduce_half | -0.000725 | -0.000480 | 0.399576 | 0.105583 | 0.081064 | -0.057424 | 0.000000 |
| fixed_20d | day8_stagnation_exit | -0.151207 | -0.103274 | 0.519382 | -0.272406 | -0.069418 | 0.062382 | 0.000000 |
| fixed_20d | day8_stagnation_exit_lt0 | -0.151207 | -0.103274 | 0.519382 | -0.272406 | -0.069418 | 0.062382 | 0.000000 |
| fixed_20d | day8_stagnation_exit_lt2 | -0.383403 | -0.274946 | 0.642928 | -1.056916 | -0.301614 | 0.185928 | 0.000000 |
| risk_budget_0p005 | baseline | 0.106070 | 0.068953 | 0.144072 | 0.843448 | 0.000000 | 0.000000 | 0.000000 |
| risk_budget_0p005 | day3_underwater_exit | 0.125738 | 0.081488 | 0.092392 | 0.853740 | 0.019668 | -0.051680 | 0.000000 |
| risk_budget_0p005 | day3_underwater_reduce_half | 0.114513 | 0.074343 | 0.124676 | 0.988971 | 0.008443 | -0.019396 | 0.000000 |
| risk_budget_0p005 | day5_no_progress_reduce_half | 0.027929 | 0.018387 | 0.148131 | 0.289597 | -0.078141 | 0.004059 | 0.000000 |
| risk_budget_0p005 | day5_underwater_exit | 0.208991 | 0.133746 | 0.112296 | 1.362104 | 0.102921 | -0.031776 | 0.000000 |
| risk_budget_0p005 | day5_underwater_reduce_half | 0.123650 | 0.080161 | 0.130767 | 1.033111 | 0.017580 | -0.013305 | 0.000000 |
| risk_budget_0p005 | day8_stagnation_exit | 0.006180 | 0.004105 | 0.206707 | 0.090371 | -0.099890 | 0.062635 | 0.000000 |
| risk_budget_0p005 | day8_stagnation_exit_lt0 | 0.006180 | 0.004105 | 0.206707 | 0.090371 | -0.099890 | 0.062635 | 0.000000 |
| risk_budget_0p005 | day8_stagnation_exit_lt2 | -0.010926 | -0.007278 | 0.215589 | -0.030246 | -0.116996 | 0.071517 | 0.000000 |
| risk_budget_0p010 | baseline | 0.147513 | 0.095279 | 0.267600 | 0.653023 | 0.000000 | 0.000000 | 0.000000 |
| risk_budget_0p010 | day3_underwater_exit | 0.222111 | 0.141870 | 0.166244 | 0.830429 | 0.074598 | -0.101356 | 0.000000 |
| risk_budget_0p010 | day3_underwater_reduce_half | 0.167665 | 0.107963 | 0.233385 | 0.792659 | 0.020152 | -0.034215 | 0.000000 |
| risk_budget_0p010 | day5_no_progress_reduce_half | 0.020660 | 0.013618 | 0.274352 | 0.166395 | -0.126853 | 0.006752 | 0.000000 |
| risk_budget_0p010 | day5_underwater_exit | 0.365943 | 0.229072 | 0.212723 | 1.225375 | 0.218430 | -0.054877 | 0.000000 |
| risk_budget_0p010 | day5_underwater_reduce_half | 0.187479 | 0.120364 | 0.243304 | 0.849270 | 0.039966 | -0.024296 | 0.000000 |
| risk_budget_0p010 | day8_stagnation_exit | -0.047080 | -0.031556 | 0.375399 | -0.087181 | -0.194593 | 0.107799 | 0.000000 |
| risk_budget_0p010 | day8_stagnation_exit_lt0 | -0.047080 | -0.031556 | 0.375399 | -0.087181 | -0.194593 | 0.107799 | 0.000000 |
| risk_budget_0p010 | day8_stagnation_exit_lt2 | -0.071850 | -0.048368 | 0.384555 | -0.184987 | -0.219363 | 0.116955 | 0.000000 |

## Recommendation

{"blocked_by_data_quality": true, "candidate_rules": [], "data_gate_blockers": ["liquidity thresholds have no passing known rows", "price paths still contain missing adjustment factors"], "no_progress_exit": "research_only", "reason": "Path-mode relative leads require non-worse fixed and risk-budget return/drawdown, but paper-trading candidates stay blocked while data gates fail.", "research_leads": ["day3_underwater_exit", "day3_underwater_reduce_half", "day5_underwater_exit", "day5_underwater_reduce_half"]}
