# 2026-07 Batch 3 Data Blocker Resolution Report

- status: blocked
- calendar_gate_fallback_ratio: 0.342229
- trading_day_gate_fallback_ratio: 0.000000
- true_trading_day_missing_count: 0
- true_trading_day_missing_ratio: 0.000000
- calendar_missing_classification: non_trading_dates_only
- calendar_missing_not_trading_day_count: 218
- liquidity_unit_status: unverified
- adjustment_missing_ratio: 0.175922
- clean_subset_share: 0.112591

## Gate Exposure

- supplement_window_rows: 418

### Supplement Mapping Assessment

{"exposure_fields": [], "reason": "supplement table has rows but lacks an explicit exposure field; it cannot be treated as persisted market_gate.exposure without replaying the benchmark/gate calculation", "state_fields": [], "supplement_only_fields": ["breadth_5d", "limit_up_quality_ok"], "usable_as_exposure_history": false}

The supplement table is treated as an input table, not usable exposure history, unless it contains explicit exposure/state fields with formula lineage.

### Trading-Day Validation Sources

| table | status | rows | first | last | source_versions | rule_versions |
|---|---|---:|---|---|---|---|
| fact_choice_macro_daily | ready | 419 | 2024-09-25 | 2026-06-23 | [{"value": "sv_tushare_index_daily_d98b61dd0c1d", "count": 306}, {"value": "sv_tushare_index_daily_61bfe54e9e84", "count": 113}] | [{"value": "rv_cross_asset_macro_environment_backfill_v1", "count": 306}, {"value": "rv_public_cross_asset_headline_v1", "count": 113}] |
| choice_market_snapshot | empty | 0 | None | None | [] | [] |

### Replay Sources

| source | exists | rows | first | last | usable_as_exposure_history |
|---|---|---:|---|---|---|
| choice_market_snapshot | True | 0 | None | None | None |
| fact_choice_macro_daily | True | 419 | 2024-09-25 | 2026-06-23 | None |
| fact_livermore_gate_supplement_daily | True | 418 | 2024-09-25 | 2026-06-22 | False |

## Liquidity Unit

### Source Lineage

{"canonical_field_status": "daily_amount_rmb_unconfirmed", "field_keys_json": [{"count": 2195813, "value": "[\"daily_limit_flags\",\"daily_ohlcv_amount\",\"daily_return_turnover_amplitude\",\"daily_trade_status\"]"}], "field_mapping": "choice_stock_materialize maps upstream AMOUNT/VOLUME/CLOSE directly to amount/volume/close_value; Batch3 consumes amount as daily_amount.", "local_evidence_conclusion": "Local lineage confirms pass-through storage, not the vendor unit. daily_amount_rmb must stay unconfirmed until vendor documentation or upstream metadata proves the conversion.", "row_count_with_amount": 2195813, "rule_versions": [{"count": 2195813, "value": "rv_choice_stock_materialization_front_layer_v1"}], "source_table": "choice_stock_daily_observation", "source_versions": [{"count": 782341, "value": "sv_choice_stock_e134c710acc5"}, {"count": 590214, "value": "sv_choice_stock_43e02a042578"}, {"count": 520679, "value": "sv_choice_stock_e0bdfba9cb65"}, {"count": 189436, "value": "sv_choice_stock_09d10e1924ff"}, {"count": 51447, "value": "sv_choice_stock_d41c81f6add3"}], "status": "ready", "vendor_versions": [{"count": 782341, "value": "vv_choice_tushare_stock_20260626_e134c710acc5"}, {"count": 590214, "value": "vv_choice_tushare_stock_20251205_43e02a042578"}, {"count": 520679, "value": "vv_choice_tushare_stock_20250303_e0bdfba9cb65"}, {"count": 189436, "value": "vv_choice_tushare_stock_20250624_09d10e1924ff"}, {"count": 51447, "value": "vv_choice_tushare_stock_20260529_d41c81f6add3"}]}

### Unit Diagnostics

{"amount_over_volume_x_close_median": 0.099737, "amount_over_volume_x_close_p10": 0.098817, "amount_over_volume_x_close_p90": 0.100719, "interpretation": "Near 1 suggests amount in currency with volume in shares; near 100 suggests amount in currency with volume in lots; near 0.1 suggests a scaled amount field with lot-based volume. Vendor confirmation is still required.", "sample_count": 20000, "status": "ready", "unit_hypothesis": "consistent_with_scaled_amount_and_lot_volume"}

### Raw Thresholds

| threshold | pass_count | fail_count | missing_count |
|---:|---:|---:|---:|
| 20000000.000000 | 0 | 826 | 0 |
| 50000000.000000 | 0 | 826 | 0 |
| 100000000.000000 | 0 | 826 | 0 |
| 200000000.000000 | 0 | 826 | 0 |

### Scale Hypotheses

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

## Adjustment Factors

- missing_adjustment_factor_rows: 3564
- missing_adjustment_factor_ratio: 0.175922
- clean_subset_share: 0.112591
- sample_selection_warning: clean subset may be biased because only paths with complete adjustment factors remain

## Blockers

- adjustment factor gaps remain in price paths
- clean adjustment subset share is below 80%
- daily_amount upstream unit remains unconfirmed
- raw liquidity thresholds still have zero passing rows

Stop condition: promotion studies stay blocked until trading-day gate fallback is validated, liquidity unit is confirmed, and adjustment coverage is adequate. Natural calendar gaps validated as non-trading dates are pipeline warnings.
