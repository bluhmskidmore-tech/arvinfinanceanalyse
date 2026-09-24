# 2026-07 Batch 3 Hold-Progress Exit Simulation Report

- status: research_only
- signal_kind: stock_candidate
- evaluated_position_rule_rows: 8230
- recommendation: research_only
- portfolio_engine_mode: horizon_diagnostic
- portfolio_comparison_scope: diagnostic_only_not_comparable_to_path_mode_risk_report
- position_level_csv: docs\pnl\batch3_hold_progress_exit_positions.csv
- portfolio_level_csv: docs\pnl\batch3_hold_progress_exit_portfolio.csv

Portfolio comparison below is diagnostic-only when `portfolio_engine_mode` is `horizon_diagnostic`; it is not comparable to the path-mode risk-budget robustness baseline.

## Rule Summary

| rule | sample_count | trigger_count | usable_trigger_count | missing_exit_count | baseline_p5 | rule_p5 | baseline_p10 | rule_p10 | missed_rebound_cost | winner_damage | fixed_20d_return_delta | fixed_20d_mdd_delta | risk_0p005_return_delta | risk_0p005_mdd_delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| day3_underwater_exit | 823 | 331 | 331 | 0 | -0.300975 | -0.217396 | -0.266414 | -0.176698 | 0.051220 | 0.042376 | 0.133629 | -0.041421 | -0.127087 | 0.049177 |
| day3_underwater_reduce_half | 823 | 331 | 331 | 0 | -0.300975 | -0.243571 | -0.266414 | -0.202586 | 0.025610 | 0.021188 | -0.009991 | 0.058312 | -0.134963 | 0.057488 |
| day5_no_progress_reduce_half | 823 | 154 | 154 | 0 | -0.213535 | -0.125808 | -0.179783 | -0.105489 | 0.025194 | 0.024878 | 0.153187 | -0.093541 | -0.014177 | -0.004548 |
| day5_underwater_exit | 823 | 394 | 394 | 0 | -0.306017 | -0.223468 | -0.270464 | -0.192989 | 0.050117 | 0.038457 | 0.477163 | -0.091076 | 0.089060 | -0.001972 |
| day5_underwater_reduce_half | 823 | 394 | 394 | 0 | -0.306017 | -0.253112 | -0.270464 | -0.211600 | 0.025059 | 0.019229 | 0.586258 | -0.052704 | 0.102546 | 0.002899 |
| day5_winner_gt5_diagnostic | 823 | 210 | 210 | 0 | -0.166100 | -0.166100 | -0.122771 | -0.122771 | 0.000000 | 0.000000 | NA | NA | NA | NA |
| day8_stagnation_exit | 823 | 523 | 523 | 0 | -0.293025 | -0.254100 | -0.252382 | -0.199236 | 0.050335 | 0.036021 | -0.323306 | 0.160038 | -0.145550 | 0.055370 |
| day8_stagnation_exit_lt0 | 823 | 523 | 523 | 0 | -0.293025 | -0.254100 | -0.252382 | -0.199236 | 0.050335 | 0.036021 | -0.323306 | 0.160038 | -0.145550 | 0.055370 |
| day8_stagnation_exit_lt2 | 823 | 564 | 564 | 0 | -0.289858 | -0.251139 | -0.249535 | -0.194445 | 0.052717 | 0.039424 | -0.064380 | 0.013547 | -0.117992 | 0.018767 |
| day8_winner_gt5_diagnostic | 823 | 201 | 201 | 0 | -0.130100 | -0.130100 | -0.095992 | -0.095992 | 0.000000 | 0.000000 | NA | NA | NA | NA |

## Forward Residual Return

| day | rule | sample_count | avg_residual_return | p10_residual_return |
|---:|---|---:|---:|---:|
| 3 | day3_underwater_exit | 331 | 0.001857 | -0.129691 |
| 3 | day3_underwater_reduce_half | 331 | 0.001857 | -0.129691 |
| 5 | day5_no_progress_reduce_half | 154 | 0.000683 | -0.148730 |
| 5 | day5_underwater_exit | 394 | 0.004230 | -0.140979 |
| 5 | day5_underwater_reduce_half | 394 | 0.004230 | -0.140979 |
| 8 | day8_stagnation_exit | 523 | 0.011219 | -0.126425 |
| 8 | day8_stagnation_exit_lt0 | 523 | 0.011219 | -0.126425 |
| 8 | day8_stagnation_exit_lt2 | 564 | 0.012868 | -0.126597 |

## Portfolio Comparison

| base_variant | rule | cumulative_return | cagr | max_drawdown | daily_sharpe | return_delta_vs_baseline | max_drawdown_delta_vs_baseline |
|---|---|---:|---:|---:|---:|---:|---:|
| fixed_20d | baseline | 0.194369 | 0.150129 | 0.283478 | 0.662028 | 0.000000 | 0.000000 |
| fixed_20d | day3_underwater_exit | 0.327998 | 0.252957 | 0.242057 | 0.813337 | 0.133629 | -0.041421 |
| fixed_20d | day3_underwater_reduce_half | 0.184378 | 0.143988 | 0.341790 | 0.544997 | -0.009991 | 0.058312 |
| fixed_20d | day5_no_progress_reduce_half | 0.347556 | 0.264789 | 0.189937 | 0.924464 | 0.153187 | -0.093541 |
| fixed_20d | day5_underwater_exit | 0.671532 | 0.500561 | 0.192402 | 1.194901 | 0.477163 | -0.091076 |
| fixed_20d | day5_underwater_reduce_half | 0.780627 | 0.577410 | 0.230774 | 1.313167 | 0.586258 | -0.052704 |
| fixed_20d | day8_stagnation_exit | -0.128937 | -0.103930 | 0.443516 | -0.155797 | -0.323306 | 0.160038 |
| fixed_20d | day8_stagnation_exit_lt0 | -0.128937 | -0.103930 | 0.443516 | -0.155797 | -0.323306 | 0.160038 |
| fixed_20d | day8_stagnation_exit_lt2 | 0.129989 | 0.102705 | 0.297025 | 0.443057 | -0.064380 | 0.013547 |
| risk_budget_0p005 | baseline | 0.211080 | 0.162783 | 0.052040 | 1.319607 | 0.000000 | 0.000000 |
| risk_budget_0p005 | day3_underwater_exit | 0.083993 | 0.066214 | 0.101217 | 0.572443 | -0.127087 | 0.049177 |
| risk_budget_0p005 | day3_underwater_reduce_half | 0.076117 | 0.060051 | 0.109528 | 0.521661 | -0.134963 | 0.057488 |
| risk_budget_0p005 | day5_no_progress_reduce_half | 0.196903 | 0.152050 | 0.047492 | 1.377057 | -0.014177 | -0.004548 |
| risk_budget_0p005 | day5_underwater_exit | 0.300140 | 0.230407 | 0.050068 | 1.596806 | 0.089060 | -0.001972 |
| risk_budget_0p005 | day5_underwater_reduce_half | 0.313626 | 0.240478 | 0.054939 | 1.647860 | 0.102546 | 0.002899 |
| risk_budget_0p005 | day8_stagnation_exit | 0.065530 | 0.051752 | 0.107410 | 0.489701 | -0.145550 | 0.055370 |
| risk_budget_0p005 | day8_stagnation_exit_lt0 | 0.065530 | 0.051752 | 0.107410 | 0.489701 | -0.145550 | 0.055370 |
| risk_budget_0p005 | day8_stagnation_exit_lt2 | 0.093088 | 0.073802 | 0.070807 | 0.647623 | -0.117992 | 0.018767 |
| risk_budget_0p010 | baseline | 0.362981 | 0.276177 | 0.101548 | 1.259886 | 0.000000 | 0.000000 |
| risk_budget_0p010 | day3_underwater_exit | 0.157853 | 0.123573 | 0.194261 | 0.619920 | -0.205128 | 0.092713 |
| risk_budget_0p010 | day3_underwater_reduce_half | 0.137933 | 0.108180 | 0.209259 | 0.554569 | -0.225048 | 0.107711 |
| risk_budget_0p010 | day5_no_progress_reduce_half | 0.370014 | 0.281359 | 0.094983 | 1.289517 | 0.007033 | -0.006565 |
| risk_budget_0p010 | day5_underwater_exit | 0.581026 | 0.436004 | 0.099046 | 1.586724 | 0.218045 | -0.002502 |
| risk_budget_0p010 | day5_underwater_reduce_half | 0.609650 | 0.456503 | 0.108985 | 1.633682 | 0.246669 | 0.007437 |
| risk_budget_0p010 | day8_stagnation_exit | 0.012735 | 0.010110 | 0.264282 | 0.150739 | -0.350246 | 0.162734 |
| risk_budget_0p010 | day8_stagnation_exit_lt0 | 0.012735 | 0.010110 | 0.264282 | 0.150739 | -0.350246 | 0.162734 |
| risk_budget_0p010 | day8_stagnation_exit_lt2 | 0.061547 | 0.048942 | 0.203986 | 0.321159 | -0.301434 | 0.102438 |

## Recommendation

{"candidate_rules": [], "mode_consistent_with_risk_report": false, "no_progress_exit": "research_only", "portfolio_engine_mode": "horizon_diagnostic", "portfolio_rejected_rules": ["day3_underwater_reduce_half", "day5_no_progress_reduce_half", "day5_underwater_reduce_half"], "position_level_candidate_rules": ["day3_underwater_reduce_half", "day5_no_progress_reduce_half", "day5_underwater_reduce_half"], "reason": "paper-trading candidates require position-level left-tail improvement, controlled winner damage, non-worse portfolio return/drawdown, and path-mode consistency.", "status": "research_only"}
