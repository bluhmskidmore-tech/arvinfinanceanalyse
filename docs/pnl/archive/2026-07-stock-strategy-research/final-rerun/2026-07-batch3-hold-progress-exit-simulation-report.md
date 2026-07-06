# 2026-07 Batch 3 Hold-Progress Exit Simulation Report

- status: research_only
- signal_kind: stock_candidate
- evaluated_position_rule_rows: 6584
- recommendation: research_only
- portfolio_engine_mode: horizon_diagnostic
- portfolio_comparison_scope: diagnostic_only_not_comparable_to_path_mode_risk_report
- position_level_csv: docs\pnl\batch3_hold_progress_exit_positions.csv
- portfolio_level_csv: docs\pnl\batch3_hold_progress_exit_portfolio.csv

Portfolio comparison below is diagnostic-only when `portfolio_engine_mode` is `horizon_diagnostic`; it is not comparable to the path-mode risk-budget robustness baseline.

## Rule Summary

| rule | sample_count | trigger_count | usable_trigger_count | missing_exit_count | baseline_p5 | rule_p5 | baseline_p10 | rule_p10 | missed_rebound_cost | winner_damage | fixed_20d_return_delta | fixed_20d_mdd_delta | risk_0p005_return_delta | risk_0p005_mdd_delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| day3_underwater_exit | 823 | 331 | 331 | 0 | -0.300975 | -0.217396 | -0.266414 | -0.176698 | 0.051220 | 0.042376 | -0.034915 | 0.085931 | -0.126163 | 0.049177 |
| day3_underwater_reduce_half | 823 | 331 | 331 | 0 | -0.300975 | -0.243571 | -0.266414 | -0.202586 | 0.025610 | 0.021188 | -0.170692 | 0.160259 | -0.156091 | 0.060986 |
| day5_no_progress_reduce_half | 823 | 154 | 154 | 0 | -0.213535 | -0.125808 | -0.179783 | -0.105489 | 0.025194 | 0.024878 | -0.150089 | 0.081691 | -0.068056 | 0.024097 |
| day5_underwater_exit | 823 | 394 | 394 | 0 | -0.306017 | -0.223468 | -0.270464 | -0.192989 | 0.050117 | 0.038457 | -0.186607 | 0.139490 | -0.011698 | 0.038476 |
| day5_winner_gt5_diagnostic | 823 | 210 | 210 | 0 | -0.166100 | -0.166100 | -0.122771 | -0.122771 | 0.000000 | 0.000000 | NA | NA | NA | NA |
| day8_stagnation_exit_lt0 | 823 | 523 | 523 | 0 | -0.293025 | -0.254100 | -0.252382 | -0.199236 | 0.050335 | 0.036021 | -0.662704 | 0.337196 | -0.225237 | 0.092334 |
| day8_stagnation_exit_lt2 | 823 | 564 | 564 | 0 | -0.289858 | -0.251139 | -0.249535 | -0.194445 | 0.052717 | 0.039424 | -0.512328 | 0.251464 | -0.170842 | 0.057246 |
| day8_winner_gt5_diagnostic | 823 | 201 | 201 | 0 | -0.130100 | -0.130100 | -0.095992 | -0.095992 | 0.000000 | 0.000000 | NA | NA | NA | NA |

## Forward Residual Return

| day | rule | sample_count | avg_residual_return | p10_residual_return |
|---:|---|---:|---:|---:|
| 3 | day3_underwater_exit | 331 | 0.001857 | -0.129691 |
| 3 | day3_underwater_reduce_half | 331 | 0.001857 | -0.129691 |
| 5 | day5_no_progress_reduce_half | 154 | 0.000683 | -0.148730 |
| 5 | day5_underwater_exit | 394 | 0.004230 | -0.140979 |
| 8 | day8_stagnation_exit_lt0 | 523 | 0.011219 | -0.126425 |
| 8 | day8_stagnation_exit_lt2 | 564 | 0.012868 | -0.126597 |

## Portfolio Comparison

| base_variant | rule | cumulative_return | cagr | max_drawdown | daily_sharpe | return_delta_vs_baseline | max_drawdown_delta_vs_baseline |
|---|---|---:|---:|---:|---:|---:|---:|
| fixed_20d | baseline | 0.430006 | 0.325344 | 0.225354 | 1.077988 | 0.000000 | 0.000000 |
| fixed_20d | day3_underwater_exit | 0.395091 | 0.303023 | 0.311285 | 0.849489 | -0.034915 | 0.085931 |
| fixed_20d | day3_underwater_reduce_half | 0.259314 | 0.201163 | 0.385613 | 0.641064 | -0.170692 | 0.160259 |
| fixed_20d | day5_no_progress_reduce_half | 0.279917 | 0.214523 | 0.307045 | 0.803101 | -0.150089 | 0.081691 |
| fixed_20d | day5_underwater_exit | 0.243399 | 0.187789 | 0.364844 | 0.605917 | -0.186607 | 0.139490 |
| fixed_20d | day8_stagnation_exit_lt0 | -0.232698 | -0.189872 | 0.562550 | -0.390736 | -0.662704 | 0.337196 |
| fixed_20d | day8_stagnation_exit_lt2 | -0.082322 | -0.066418 | 0.476818 | 0.009830 | -0.512328 | 0.251464 |
| risk_budget_0p005 | baseline | 0.332986 | 0.254007 | 0.052040 | 1.666628 | 0.000000 | 0.000000 |
| risk_budget_0p005 | day3_underwater_exit | 0.206823 | 0.161189 | 0.101217 | 1.083964 | -0.126163 | 0.049177 |
| risk_budget_0p005 | day3_underwater_reduce_half | 0.176895 | 0.138238 | 0.113026 | 0.938570 | -0.156091 | 0.060986 |
| risk_budget_0p005 | day5_no_progress_reduce_half | 0.264930 | 0.203309 | 0.076137 | 1.632932 | -0.068056 | 0.024097 |
| risk_budget_0p005 | day5_underwater_exit | 0.321288 | 0.246190 | 0.090516 | 1.482972 | -0.011698 | 0.038476 |
| risk_budget_0p005 | day8_stagnation_exit_lt0 | 0.107749 | 0.084748 | 0.144374 | 0.647066 | -0.225237 | 0.092334 |
| risk_budget_0p005 | day8_stagnation_exit_lt2 | 0.162144 | 0.127738 | 0.109286 | 0.891963 | -0.170842 | 0.057246 |
| risk_budget_0p010 | baseline | 0.708215 | 0.524499 | 0.101548 | 1.637358 | 0.000000 | 0.000000 |
| risk_budget_0p010 | day3_underwater_exit | 0.406116 | 0.311203 | 0.194326 | 1.059752 | -0.302099 | 0.092778 |
| risk_budget_0p010 | day3_underwater_reduce_half | 0.336142 | 0.259061 | 0.222933 | 0.913114 | -0.372073 | 0.121385 |
| risk_budget_0p010 | day5_no_progress_reduce_half | 0.550293 | 0.412377 | 0.149126 | 1.592456 | -0.157922 | 0.047578 |
| risk_budget_0p010 | day5_underwater_exit | 0.690002 | 0.513644 | 0.174722 | 1.476508 | -0.018213 | 0.073174 |
| risk_budget_0p010 | day8_stagnation_exit_lt0 | 0.134680 | 0.105660 | 0.309867 | 0.491498 | -0.573535 | 0.208319 |
| risk_budget_0p010 | day8_stagnation_exit_lt2 | 0.238423 | 0.186575 | 0.253307 | 0.726527 | -0.469792 | 0.151759 |

## Recommendation

{"candidate_rules": [], "mode_consistent_with_risk_report": false, "no_progress_exit": "research_only", "portfolio_engine_mode": "horizon_diagnostic", "portfolio_rejected_rules": ["day3_underwater_reduce_half", "day5_no_progress_reduce_half"], "position_level_candidate_rules": ["day3_underwater_reduce_half", "day5_no_progress_reduce_half"], "reason": "paper-trading candidates require position-level left-tail improvement, controlled winner damage, non-worse portfolio return/drawdown, and path-mode consistency.", "status": "research_only"}
