# 2026-07 Batch 3 Liquidity Unit Capacity Report

- status: blocked
- unit_status: unverified
- source_field: choice_stock_daily_observation.amount loaded as daily_amount in execution backtest inputs
- interpretation: If daily_amount is RMB, the candidate pool is below executable capacity. If it is not RMB, upstream unit mapping must be fixed before readiness can improve.
- thresholds_all_fail: True

## Daily Amount Distribution

- row_count: 826
- known_count: 826
- missing_count: 0
- coverage_ratio: 1.000000
- min: 26436.330000
- median: 678639.815000
- p90: 2931913.079000
- max: 17572905.892000

## Capacity Thresholds

| threshold_rmb | pass_count | fail_count | missing_count | pass_ratio |
|---:|---:|---:|---:|---:|
| 20000000.000000 | 0 | 826 | 0 | 0.000000 |
| 50000000.000000 | 0 | 826 | 0 | 0.000000 |
| 100000000.000000 | 0 | 826 | 0 | 0.000000 |
| 200000000.000000 | 0 | 826 | 0 | 0.000000 |

Conclusion: keep this report blocked until the upstream unit is explicitly confirmed. If the unit is RMB, current capacity is unusable at the tested thresholds; if the unit is not RMB, convert upstream and rerun.
