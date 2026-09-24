# 2026-07 Batch 2 Gate State Flip Diagnostic

- status: ready
- db_path: data\moss.duckdb
- benchmark_tables: choice_market_snapshot, fact_choice_macro_daily
- conclusion: delayed_downgrade_hurt_timing
- transition_count: 16
- annualized_transition_count: 34.758621
- whipsaw_count: 7
- whipsaw_ratio: 0.437500
- cumulative_return_delta: -0.022617
- missing_gate_days: 0

## Line Metrics

| line | terminal_value | cumulative_return | cagr | max_drawdown | daily_sharpe |
|---|---:|---:|---:|---:|---:|
| immediate_index | 106.607102 | 0.066071 | 0.150503 | 0.049837 | 1.477830 |
| delayed_downgrade_index | 104.345413 | 0.043454 | 0.097693 | 0.062305 | 0.882423 |

## Dwell

| state | avg_dwell_days |
|---|---:|
| HOT | 3.428571 |
| OVERHEAT | 4.000000 |
| PENDING_DATA | 59.000000 |
| WARM | 3.250000 |
