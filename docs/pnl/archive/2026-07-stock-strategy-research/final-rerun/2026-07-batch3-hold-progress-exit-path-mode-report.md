# 2026-07 Batch 3 Hold-Progress Exit Path-Mode Report

- status: research_only
- engine_mode: path_mode_report_layer_v1
- position_level_csv: docs\pnl\batch3_hold_progress_exit_path_mode_positions.csv
- recommendation: research_only

This simulation exits on the day-k trigger's next tradable open and does not use future path data to decide the trigger. It remains report-layer only.

## Rule Summary

| rule | fixed_20d_return_delta | fixed_20d_mdd_delta | risk_0p005_return_delta | risk_0p005_mdd_delta | risk_0p010_return_delta | risk_0p010_mdd_delta |
|---|---:|---:|---:|---:|---:|---:|
| day3_underwater_exit | -0.046856 | 0.039841 | -0.123341 | 0.031052 | -0.296418 | 0.062363 |
| day3_underwater_reduce_half | 0.102371 | -0.056903 | -0.005542 | -0.003715 | -0.014981 | -0.007168 |
| day5_no_progress_reduce_half | -0.147912 | -0.003067 | -0.094618 | 0.001234 | -0.216697 | 0.002259 |
| day5_underwater_exit | -0.015495 | 0.069734 | -0.012963 | 0.030313 | -0.030762 | 0.054542 |
| day8_stagnation_exit_lt0 | -0.676257 | 0.274253 | -0.225628 | 0.084402 | -0.581825 | 0.185202 |
| day8_stagnation_exit_lt2 | -0.538969 | 0.204623 | -0.171048 | 0.046089 | -0.476954 | 0.126710 |

## Portfolio Comparison

| base_variant | rule | cumulative_return | cagr | max_drawdown | daily_sharpe | return_delta_vs_baseline | max_drawdown_delta_vs_baseline | exposure_fallback_day_ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| fixed_20d | baseline | 0.436298 | 0.270586 | 0.340518 | 0.855892 | 0.000000 | 0.000000 | 0.774869 |
| fixed_20d | day3_underwater_exit | 0.389442 | 0.243017 | 0.380359 | 0.823203 | -0.046856 | 0.039841 | 0.774869 |
| fixed_20d | day3_underwater_reduce_half | 0.538669 | 0.329784 | 0.283615 | 1.051190 | 0.102371 | -0.056903 | 0.774869 |
| fixed_20d | day5_no_progress_reduce_half | 0.288386 | 0.182460 | 0.337451 | 0.674094 | -0.147912 | -0.003067 | 0.774869 |
| fixed_20d | day5_underwater_exit | 0.420803 | 0.261504 | 0.410252 | 0.833782 | -0.015495 | 0.069734 | 0.774869 |
| fixed_20d | day8_stagnation_exit_lt0 | -0.239959 | -0.166765 | 0.614771 | -0.330274 | -0.676257 | 0.274253 | 0.776316 |
| fixed_20d | day8_stagnation_exit_lt2 | -0.102671 | -0.069498 | 0.545141 | -0.002412 | -0.538969 | 0.204623 | 0.776316 |
| risk_budget_0p005 | baseline | 0.331108 | 0.208250 | 0.099721 | 1.636345 | 0.000000 | 0.000000 | 0.774869 |
| risk_budget_0p005 | day3_underwater_exit | 0.207767 | 0.132988 | 0.130773 | 1.250743 | -0.123341 | 0.031052 | 0.774869 |
| risk_budget_0p005 | day3_underwater_reduce_half | 0.325566 | 0.204920 | 0.096006 | 1.732378 | -0.005542 | -0.003715 | 0.774869 |
| risk_budget_0p005 | day5_no_progress_reduce_half | 0.236490 | 0.150738 | 0.100955 | 1.327699 | -0.094618 | 0.001234 | 0.774869 |
| risk_budget_0p005 | day5_underwater_exit | 0.318145 | 0.200455 | 0.130034 | 1.539194 | -0.012963 | 0.030313 | 0.774869 |
| risk_budget_0p005 | day8_stagnation_exit_lt0 | 0.105480 | 0.068950 | 0.184123 | 0.577438 | -0.225628 | 0.084402 | 0.776316 |
| risk_budget_0p005 | day8_stagnation_exit_lt2 | 0.160060 | 0.103757 | 0.145810 | 0.784355 | -0.171048 | 0.046089 | 0.776316 |
| risk_budget_0p010 | baseline | 0.707692 | 0.424688 | 0.186843 | 1.627916 | 0.000000 | 0.000000 | 0.774869 |
| risk_budget_0p010 | day3_underwater_exit | 0.411274 | 0.255901 | 0.249206 | 1.222979 | -0.296418 | 0.062363 | 0.774869 |
| risk_budget_0p010 | day3_underwater_reduce_half | 0.692711 | 0.416409 | 0.179675 | 1.717986 | -0.014981 | -0.007168 | 0.774869 |
| risk_budget_0p010 | day5_no_progress_reduce_half | 0.490995 | 0.302387 | 0.189102 | 1.331468 | -0.216697 | 0.002259 | 0.774869 |
| risk_budget_0p010 | day5_underwater_exit | 0.676930 | 0.407661 | 0.241385 | 1.535264 | -0.030762 | 0.054542 | 0.774869 |
| risk_budget_0p010 | day8_stagnation_exit_lt0 | 0.125867 | 0.082017 | 0.372045 | 0.462371 | -0.581825 | 0.185202 | 0.776316 |
| risk_budget_0p010 | day8_stagnation_exit_lt2 | 0.230738 | 0.148026 | 0.313553 | 0.680415 | -0.476954 | 0.126710 | 0.776316 |

## Recommendation

{"candidate_rules": [], "no_progress_exit": "research_only", "reason": "Path-mode candidates require non-worse fixed and risk-budget return/drawdown; current output remains no-go unless candidate_rules is non-empty."}
