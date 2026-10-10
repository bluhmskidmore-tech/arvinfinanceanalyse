# 2026-07 Batch 2 OVERHEAT Holdings Diagnostic

- status: ready
- db_path: data\moss.duckdb
- conclusion: overheat_holding_blindspot_needs_rule_research
- sample_count: 6
- price_basis: raw_close_missing_adjustment_factor
- adjustment_factor_missing_rows: 105
- risk_exit_formula_version: rv_livermore_risk_exit_ema10_volume_obsfallback_v3
- overheat_sample_count: 5
- overheat_blindspot_ratio: 0.666667

## State Summary

| state | samples | stocks | horizon | avg_net_return | win_rate | avg_max_drawdown |
|---|---:|---:|---|---:|---:|---:|
| HOT | 1 | 1 | 5d | 0.167494 | 1.000000 | 0.003350 |
| HOT | 1 | 1 | 10d | NA | NA | NA |
| HOT | 1 | 1 | 20d | NA | NA | NA |
| OVERHEAT | 5 | 1 | 5d | -0.109169 | 0.500000 | 0.176151 |
| OVERHEAT | 5 | 1 | 10d | -0.220807 | 0.000000 | 0.259037 |
| OVERHEAT | 5 | 1 | 20d | -0.220716 | 0.000000 | 0.382725 |

## Rule Candidates

- Evaluate OVERHEAT exposure downgrade for existing holdings; estimated sample reach 5 holding-days.
- Evaluate tighter trailing exit under OVERHEAT when current risk_exit is not triggered; estimated sample reach 5 holding-days.
