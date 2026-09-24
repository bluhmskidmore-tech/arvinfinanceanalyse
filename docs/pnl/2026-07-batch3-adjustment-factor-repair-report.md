# 2026-07 Batch 3 Adjustment Factor Repair Report

- status: blocked
- live_strategy_changes: none
- missing_factor_rows: 3564
- missing_ratio: 0.175922
- affected_symbol_count: 628
- affected_date_count: 61
- affected_trade_count: 733
- clean_subset_share: 0.112591

## Source Inventory

| table | row_count | columns |
|---|---:|---|
| choice_stock_factor_snapshot | 94026 | as_of_date, dividend_yield, gross_margin, industry, pb, pe, ps, roe, rule_version, run_id, source_version, stock_code, three_month_return, twelve_month_return, vendor_version, volatility |
| fact_formal_pnl_fi | 24474 | manual_adjustment |
| fact_nonstd_pnl_bridge | 2438 | manual_adjustment |
| livermore_candidate_execution_history | 5532 | price_adjustment_mode, return_10d_gross_adj, return_10d_net_adj, return_1d_gross_adj, return_1d_net_adj, return_20d_gross_adj, return_20d_net_adj, return_5d_gross_adj, return_5d_net_adj |
| livermore_candidate_history | 5532 | return_10d_adj, return_1d_adj, return_20d_adj, return_5d_adj |
| livermore_stock_candidate_universe_history | 1192 | return_10d_adj, return_1d_adj, return_20d_adj, return_5d_adj |
| position_snapshot | 14731 | manual_impairment_adjustment |
| stock_adjustment_factor | 589256 | adj_factor, run_id, source_version, stock_code, trade_date |

## Denominator Scopes

- denominator_scope_source: canonical_research_dataset
- engine_path_rows: 20259
- engine_missing_adjustment_factor_rows: 3564
- engine_missing_adjustment_factor_ratio: 0.175922
- canonical_path_rows: 20634
- canonical_missing_adjustment_factor_rows: 3570
- canonical_missing_adjustment_factor_ratio: 0.173015
- within_horizon_path_rows: 15677
- within_horizon_missing_adjustment_factor_rows: 2548
- within_horizon_missing_adjustment_factor_ratio: 0.162531
- denominator_scope_note: engine_path_rows count raw loaded path rows; canonical_path_rows count emitted canonical path rows; within_horizon_path_rows excludes path rows beyond planned_exit_date.

## Coverage Detail

- affected_symbols_sample: ["000021.SZ", "000032.SZ", "000034.SZ", "000045.SZ", "000049.SZ", "000050.SZ", "000063.SZ", "000065.SZ", "000100.SZ", "000409.SZ", "000426.SZ", "000501.SZ", "000506.SZ", "000514.SZ", "000519.SZ", "000558.SZ", "000559.SZ", "000565.SZ", "000586.SZ", "000601.SZ", "000609.SZ", "000632.SZ", "000633.SZ", "000636.SZ", "000657.SZ"]
- affected_dates_sample: ["2024-09-25", "2024-10-10", "2024-10-23", "2024-10-24", "2024-11-14", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-08", "2025-01-10", "2025-01-13", "2025-01-15", "2025-01-16", "2025-01-20", "2025-01-22", "2025-01-23", "2025-01-24", "2025-03-21", "2025-04-01", "2025-04-02", "2025-04-03", "2025-04-07", "2025-04-14", "2025-04-15", "2025-04-16"]
- adj_factor_table_diagnostics: `{"date_count": 350, "diagnosis": "Path-level gaps are concentrated on dates absent from the local adj_factor table; do not forward-fill factors without vendor-backed lineage.", "first_date": "2024-08-30", "last_date": "2026-06-22", "missing_path_date_count": 61, "missing_path_dates_absent_from_adj_table": 61, "missing_path_dates_present_in_adj_table": 0, "missing_path_rows": 3564, "row_count": 589256, "status": "ready", "stock_code_count": 1689, "table": "stock_adjustment_factor", "top_missing_path_dates": [{"missing_rows": 112, "trade_date": "2025-01-02"}, {"missing_rows": 109, "trade_date": "2025-03-21"}, {"missing_rows": 106, "trade_date": "2025-01-03"}, {"missing_rows": 100, "trade_date": "2025-01-06"}, {"missing_rows": 91, "trade_date": "2025-04-01"}, {"missing_rows": 90, "trade_date": "2025-01-08"}, {"missing_rows": 85, "trade_date": "2025-04-02"}, {"missing_rows": 82, "trade_date": "2025-10-28"}, {"missing_rows": 81, "trade_date": "2025-04-03"}, {"missing_rows": 80, "trade_date": "2025-04-07"}, {"missing_rows": 79, "trade_date": "2025-11-04"}, {"missing_rows": 78, "trade_date": "2025-01-10"}, {"missing_rows": 78, "trade_date": "2025-06-11"}, {"missing_rows": 78, "trade_date": "2025-11-11"}, {"missing_rows": 78, "trade_date": "2025-11-14"}, {"missing_rows": 76, "trade_date": "2025-08-12"}, {"missing_rows": 75, "trade_date": "2025-06-13"}, {"missing_rows": 75, "trade_date": "2025-06-18"}, {"missing_rows": 75, "trade_date": "2025-09-03"}, {"missing_rows": 74, "trade_date": "2025-08-13"}]}`

## Backtest Samples

- full_sample_current: `{"status": "skipped_until_adjustment_factor_blocker_clears"}`
- clean_adjustment_subset: `{"status": "skipped_until_adjustment_factor_blocker_clears"}`
- repaired_factor_sample: `{"reason": "No explicit additional factor source with the missing path dates was found; no forward-fill or future-value reconstruction was applied.", "status": "blocked"}`
- instability: `{"status": "skipped_until_repair"}`

## Blockers

- adjustment factor missing ratio is above 2%
- clean adjustment subset share is below 70%; promotion evidence would be sample-biased

No forward-fill, future adjusted-close reconstruction, or unofficial factor chain repair was applied.
