# 2026-07 Batch 3 Liquidity Canonical RMB Report

- status: blocked
- canonical_field: daily_amount_rmb_canonical
- canonical_status: blocked
- liquidity_blocked: True
- live_strategy_changes: none

## Canonical Evidence

- canonical_evidence: `{"multiplier": null, "reason": "lineage confirms pass-through only; vendor unit contract is missing", "status": "blocked", "unit_hypothesis": "consistent_with_scaled_amount_and_lot_volume"}`
- implied_unit_diagnostics: `{"amount_over_volume_x_close_median": 0.099737, "amount_over_volume_x_close_p10": 0.098817, "amount_over_volume_x_close_p90": 0.100719, "interpretation": "Near 1 suggests amount in currency with volume in shares; near 100 suggests amount in currency with volume in lots; near 0.1 suggests a scaled amount field with lot-based volume. Vendor confirmation is still required.", "sample_count": 20000, "status": "ready", "unit_hypothesis": "consistent_with_scaled_amount_and_lot_volume"}`
- source_lineage: `{"canonical_field_status": "daily_amount_rmb_unconfirmed", "field_keys_json": [{"count": 2195813, "value": "[\"daily_limit_flags\",\"daily_ohlcv_amount\",\"daily_return_turnover_amplitude\",\"daily_trade_status\"]"}], "field_mapping": "choice_stock_materialize maps upstream AMOUNT/VOLUME/CLOSE directly to amount/volume/close_value; Batch3 consumes amount as daily_amount.", "local_evidence_conclusion": "Local lineage confirms pass-through storage, not the vendor unit. daily_amount_rmb must stay unconfirmed until vendor documentation or upstream metadata proves the conversion.", "row_count_with_amount": 2195813, "rule_versions": [{"count": 2195813, "value": "rv_choice_stock_materialization_front_layer_v1"}], "source_table": "choice_stock_daily_observation", "source_versions": [{"count": 782341, "value": "sv_choice_stock_e134c710acc5"}, {"count": 590214, "value": "sv_choice_stock_43e02a042578"}, {"count": 520679, "value": "sv_choice_stock_e0bdfba9cb65"}, {"count": 189436, "value": "sv_choice_stock_09d10e1924ff"}, {"count": 51447, "value": "sv_choice_stock_d41c81f6add3"}], "status": "ready", "vendor_versions": [{"count": 782341, "value": "vv_choice_tushare_stock_20260626_e134c710acc5"}, {"count": 590214, "value": "vv_choice_tushare_stock_20251205_43e02a042578"}, {"count": 520679, "value": "vv_choice_tushare_stock_20250303_e0bdfba9cb65"}, {"count": 189436, "value": "vv_choice_tushare_stock_20250624_09d10e1924ff"}, {"count": 51447, "value": "vv_choice_tushare_stock_20260529_d41c81f6add3"}]}`

## Amount-Like Sources

| table | column | row_count | non_null_count | scan_status |
|---|---|---:|---:|---|
| choice_stock_daily_observation | amount | 3116524 | 3110110 | scanned |
| livermore_candidate_history | abnormal_turnover | 5532 | 816 | scanned |
| livermore_stock_candidate_universe_history | abnormal_turnover | 1192 | 1192 | scanned |
| fact_accounting_asset_movement_monthly | gl_amount | 87 | 87 | scanned |
| fact_accounting_asset_movement_monthly | zqtz_amount | 87 | 87 | scanned |
| fact_formal_tyw_balance_daily | accrued_interest_amount | 2267652 | 2267652 | scanned |
| fact_formal_tyw_balance_daily | principal_amount | 2267652 | 2267652 | scanned |
| fact_formal_zqtz_balance_daily | accrued_interest_amount | 1650830 | 1650830 | scanned |
| fact_formal_zqtz_balance_daily | amortized_cost_amount | 1650830 | 1650830 | scanned |
| fact_formal_zqtz_balance_daily | face_value_amount | 1650830 | 1650830 | scanned |
| fact_formal_zqtz_balance_daily | market_value_amount | 1650830 | 1650830 | scanned |
| phase1_nonstd_pnl_preview_rows | raw_amount | 248664 | 248664 | scanned |
| position_snapshot | face_amount | 14731 | 14730 | scanned |
| position_snapshot_agg | asset_face_amount | 8 | 8 | scanned |
| position_snapshot_agg | liability_face_amount | 8 | 8 | scanned |
| std_external_supply_auction_calendar | amount_numeric | 18 | 16 | scanned |
| std_external_supply_auction_calendar | amount_unit | 18 | 16 | scanned |
| vw_external_supply_auction_calendar | amount_numeric | 18 | 16 | scanned |
| vw_external_supply_auction_calendar | amount_unit | 18 | 16 | scanned |

## Threshold Hypotheses

| scale | multiplier | threshold_rmb | pass | fail | unknown | median | p90 |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | 1.000000 | 5000000.000000 | 42 | 784 | 0 | 678639.815000 | 2931913.079000 |
| raw | 1.000000 | 10000000.000000 | 8 | 818 | 0 | 678639.815000 | 2931913.079000 |
| raw | 1.000000 | 20000000.000000 | 0 | 826 | 0 | 678639.815000 | 2931913.079000 |
| raw | 1.000000 | 50000000.000000 | 0 | 826 | 0 | 678639.815000 | 2931913.079000 |
| raw | 1.000000 | 100000000.000000 | 0 | 826 | 0 | 678639.815000 | 2931913.079000 |
| raw | 1.000000 | 200000000.000000 | 0 | 826 | 0 | 678639.815000 | 2931913.079000 |
| x10 | 10.000000 | 5000000.000000 | 522 | 304 | 0 | 6786398.150000 | 29319130.790000 |
| x10 | 10.000000 | 10000000.000000 | 281 | 545 | 0 | 6786398.150000 | 29319130.790000 |
| x10 | 10.000000 | 20000000.000000 | 131 | 695 | 0 | 6786398.150000 | 29319130.790000 |
| x10 | 10.000000 | 50000000.000000 | 42 | 784 | 0 | 6786398.150000 | 29319130.790000 |
| x10 | 10.000000 | 100000000.000000 | 8 | 818 | 0 | 6786398.150000 | 29319130.790000 |
| x10 | 10.000000 | 200000000.000000 | 0 | 826 | 0 | 6786398.150000 | 29319130.790000 |
| x100 | 100.000000 | 5000000.000000 | 821 | 5 | 0 | 67863981.500000 | 293191307.900000 |
| x100 | 100.000000 | 10000000.000000 | 803 | 23 | 0 | 67863981.500000 | 293191307.900000 |
| x100 | 100.000000 | 20000000.000000 | 734 | 92 | 0 | 67863981.500000 | 293191307.900000 |
| x100 | 100.000000 | 50000000.000000 | 522 | 304 | 0 | 67863981.500000 | 293191307.900000 |
| x100 | 100.000000 | 100000000.000000 | 281 | 545 | 0 | 67863981.500000 | 293191307.900000 |
| x100 | 100.000000 | 200000000.000000 | 131 | 695 | 0 | 67863981.500000 | 293191307.900000 |
| x1000 | 1000.000000 | 5000000.000000 | 826 | 0 | 0 | 678639815.000000 | 2931913079.000000 |
| x1000 | 1000.000000 | 10000000.000000 | 826 | 0 | 0 | 678639815.000000 | 2931913079.000000 |
| x1000 | 1000.000000 | 20000000.000000 | 826 | 0 | 0 | 678639815.000000 | 2931913079.000000 |
| x1000 | 1000.000000 | 50000000.000000 | 821 | 5 | 0 | 678639815.000000 | 2931913079.000000 |
| x1000 | 1000.000000 | 100000000.000000 | 803 | 23 | 0 | 678639815.000000 | 2931913079.000000 |
| x1000 | 1000.000000 | 200000000.000000 | 734 | 92 | 0 | 678639815.000000 | 2931913079.000000 |
| x10000 | 10000.000000 | 5000000.000000 | 826 | 0 | 0 | 6786398150.000000 | 29319130790.000000 |
| x10000 | 10000.000000 | 10000000.000000 | 826 | 0 | 0 | 6786398150.000000 | 29319130790.000000 |
| x10000 | 10000.000000 | 20000000.000000 | 826 | 0 | 0 | 6786398150.000000 | 29319130790.000000 |
| x10000 | 10000.000000 | 50000000.000000 | 826 | 0 | 0 | 6786398150.000000 | 29319130790.000000 |
| x10000 | 10000.000000 | 100000000.000000 | 826 | 0 | 0 | 6786398150.000000 | 29319130790.000000 |
| x10000 | 10000.000000 | 200000000.000000 | 826 | 0 | 0 | 6786398150.000000 | 29319130790.000000 |
| x100000 | 100000.000000 | 5000000.000000 | 826 | 0 | 0 | 67863981500.000000 | 293191307900.000000 |
| x100000 | 100000.000000 | 10000000.000000 | 826 | 0 | 0 | 67863981500.000000 | 293191307900.000000 |
| x100000 | 100000.000000 | 20000000.000000 | 826 | 0 | 0 | 67863981500.000000 | 293191307900.000000 |
| x100000 | 100000.000000 | 50000000.000000 | 826 | 0 | 0 | 67863981500.000000 | 293191307900.000000 |
| x100000 | 100000.000000 | 100000000.000000 | 826 | 0 | 0 | 67863981500.000000 | 293191307900.000000 |
| x100000 | 100000.000000 | 200000000.000000 | 826 | 0 | 0 | 67863981500.000000 | 293191307900.000000 |
| x1000000 | 1000000.000000 | 5000000.000000 | 826 | 0 | 0 | 678639815000.000000 | 2931913079000.000000 |
| x1000000 | 1000000.000000 | 10000000.000000 | 826 | 0 | 0 | 678639815000.000000 | 2931913079000.000000 |
| x1000000 | 1000000.000000 | 20000000.000000 | 826 | 0 | 0 | 678639815000.000000 | 2931913079000.000000 |
| x1000000 | 1000000.000000 | 50000000.000000 | 826 | 0 | 0 | 678639815000.000000 | 2931913079000.000000 |
| x1000000 | 1000000.000000 | 100000000.000000 | 826 | 0 | 0 | 678639815000.000000 | 2931913079000.000000 |
| x1000000 | 1000000.000000 | 200000000.000000 | 826 | 0 | 0 | 678639815000.000000 | 2931913079000.000000 |

## Trade Coverage At 20m RMB

- total_trade_rows: 826
- pass_count: 0
- fail_count: 826
- unknown_count: 0
- unknown_ratio: 0.000000

## Top Illiquid Contributors

| stock_code | pass | fail | unknown |
|---|---:|---:|---:|
| 600396.SH | 0 | 9 | 0 |
| 300042.SZ | 0 | 5 | 0 |
| 000823.SZ | 0 | 4 | 0 |
| 000966.SZ | 0 | 4 | 0 |
| 601016.SH | 0 | 4 | 0 |
| 002181.SZ | 0 | 3 | 0 |
| 002467.SZ | 0 | 3 | 0 |
| 002471.SZ | 0 | 3 | 0 |
| 002640.SZ | 0 | 3 | 0 |
| 002985.SZ | 0 | 3 | 0 |

## Blockers

- daily_amount_rmb_canonical is not verified by vendor/unit lineage
- raw daily_amount thresholds have zero passing rows; unit investigation remains required

No strategy conclusion may be promoted while `daily_amount_rmb_canonical` is blocked.
