# 2026-07 Batch 3 Liquidity Unit Capacity V2 Report

- status: blocked
- unit_status: unverified
- source: choice_stock_daily_observation.amount

## Raw Daily Amount

- known_count: 826
- min: 26436.330000
- median: 678639.815000
- p90: 2931913.079000
- max: 17572905.892000

## Raw Thresholds

| threshold | pass_count | fail_count | missing_count |
|---:|---:|---:|---:|
| 20000000.000000 | 0 | 826 | 0 |
| 50000000.000000 | 0 | 826 | 0 |
| 100000000.000000 | 0 | 826 | 0 |
| 200000000.000000 | 0 | 826 | 0 |

## Source Lineage

{"canonical_field_status": "daily_amount_rmb_unconfirmed", "field_keys_json": [{"count": 2195813, "value": "[\"daily_limit_flags\",\"daily_ohlcv_amount\",\"daily_return_turnover_amplitude\",\"daily_trade_status\"]"}], "field_mapping": "choice_stock_materialize maps upstream AMOUNT/VOLUME/CLOSE directly to amount/volume/close_value; Batch3 consumes amount as daily_amount.", "local_evidence_conclusion": "Local lineage confirms pass-through storage, not the vendor unit. daily_amount_rmb must stay unconfirmed until vendor documentation or upstream metadata proves the conversion.", "row_count_with_amount": 2195813, "rule_versions": [{"count": 2195813, "value": "rv_choice_stock_materialization_front_layer_v1"}], "source_table": "choice_stock_daily_observation", "source_versions": [{"count": 782341, "value": "sv_choice_stock_e134c710acc5"}, {"count": 590214, "value": "sv_choice_stock_43e02a042578"}, {"count": 520679, "value": "sv_choice_stock_e0bdfba9cb65"}, {"count": 189436, "value": "sv_choice_stock_09d10e1924ff"}, {"count": 51447, "value": "sv_choice_stock_d41c81f6add3"}], "status": "ready", "vendor_versions": [{"count": 782341, "value": "vv_choice_tushare_stock_20260626_e134c710acc5"}, {"count": 590214, "value": "vv_choice_tushare_stock_20251205_43e02a042578"}, {"count": 520679, "value": "vv_choice_tushare_stock_20250303_e0bdfba9cb65"}, {"count": 189436, "value": "vv_choice_tushare_stock_20250624_09d10e1924ff"}, {"count": 51447, "value": "vv_choice_tushare_stock_20260529_d41c81f6add3"}]}

Local lineage confirms pass-through storage from upstream AMOUNT to `choice_stock_daily_observation.amount` and then Batch3 `daily_amount`; it does not confirm a canonical `daily_amount_rmb` conversion.

## Unit Diagnostics

{"amount_over_volume_x_close_median": 0.099737, "amount_over_volume_x_close_p10": 0.098817, "amount_over_volume_x_close_p90": 0.100719, "interpretation": "Near 1 suggests amount in currency with volume in shares; near 100 suggests amount in currency with volume in lots; near 0.1 suggests a scaled amount field with lot-based volume. Vendor confirmation is still required.", "sample_count": 20000, "status": "ready", "unit_hypothesis": "consistent_with_scaled_amount_and_lot_volume"}

## Threshold Sensitivity Under Scale Hypotheses

| scale | multiplier | threshold | pass_count | fail_count | missing_count |
|---|---:|---:|---:|---:|---:|
| raw | 1.000000 | 20000000.000000 | 0 | 826 | 0 |
| raw | 1.000000 | 50000000.000000 | 0 | 826 | 0 |
| raw | 1.000000 | 100000000.000000 | 0 | 826 | 0 |
| raw | 1.000000 | 200000000.000000 | 0 | 826 | 0 |
| x1000 | 1000.000000 | 20000000.000000 | 826 | 0 | 0 |
| x1000 | 1000.000000 | 50000000.000000 | 821 | 5 | 0 |
| x1000 | 1000.000000 | 100000000.000000 | 803 | 23 | 0 |
| x1000 | 1000.000000 | 200000000.000000 | 734 | 92 | 0 |
| x10000 | 10000.000000 | 20000000.000000 | 826 | 0 | 0 |
| x10000 | 10000.000000 | 50000000.000000 | 826 | 0 | 0 |
| x10000 | 10000.000000 | 100000000.000000 | 826 | 0 | 0 |
| x10000 | 10000.000000 | 200000000.000000 | 826 | 0 | 0 |

## Blockers

- daily_amount upstream unit remains unverified
- liquidity thresholds have no passing known rows under raw unit

Stop condition: this remains blocked until the upstream amount unit is confirmed and raw/converted thresholds are explicitly justified.
