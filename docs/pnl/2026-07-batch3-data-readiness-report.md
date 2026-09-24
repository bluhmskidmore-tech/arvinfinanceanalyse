# 2026-07 Batch 3 Data Readiness Report

- status: blocked
- db_path: F:\MOSS-V3\data\moss.duckdb
- signal_kind: stock_candidate
- execution_row_count: 826

## Gate Exposure

| persisted_rows | replayed_rows | fallback_rows | fallback_ratio | missing_dates_total |
|---:|---:|---:|---:|---:|
| 0 | 419 | 218 | 0.342229 | 218 |

- missing_dates_sample: ['2024-09-28', '2024-09-29', '2024-10-01', '2024-10-02', '2024-10-03', '2024-10-04', '2024-10-05', '2024-10-06', '2024-10-07', '2024-10-12', '2024-10-13', '2024-10-19', '2024-10-20', '2024-10-26', '2024-10-27', '2024-11-02', '2024-11-03', '2024-11-09', '2024-11-10', '2024-11-16', '2024-11-17', '2024-11-23', '2024-11-24', '2024-11-30', '2024-12-01']
- missing_date_ranges: [{'start': '2024-09-28', 'end': '2024-09-29', 'days': 2}, {'start': '2024-10-01', 'end': '2024-10-07', 'days': 7}, {'start': '2024-10-12', 'end': '2024-10-13', 'days': 2}, {'start': '2024-10-19', 'end': '2024-10-20', 'days': 2}, {'start': '2024-10-26', 'end': '2024-10-27', 'days': 2}, {'start': '2024-11-02', 'end': '2024-11-03', 'days': 2}, {'start': '2024-11-09', 'end': '2024-11-10', 'days': 2}, {'start': '2024-11-16', 'end': '2024-11-17', 'days': 2}, {'start': '2024-11-23', 'end': '2024-11-24', 'days': 2}, {'start': '2024-11-30', 'end': '2024-12-01', 'days': 2}, {'start': '2024-12-07', 'end': '2024-12-08', 'days': 2}, {'start': '2024-12-14', 'end': '2024-12-15', 'days': 2}, {'start': '2024-12-21', 'end': '2024-12-22', 'days': 2}, {'start': '2024-12-28', 'end': '2024-12-29', 'days': 2}, {'start': '2025-01-01', 'end': '2025-01-01', 'days': 1}, {'start': '2025-01-04', 'end': '2025-01-05', 'days': 2}, {'start': '2025-01-11', 'end': '2025-01-12', 'days': 2}, {'start': '2025-01-18', 'end': '2025-01-19', 'days': 2}, {'start': '2025-01-25', 'end': '2025-01-26', 'days': 2}, {'start': '2025-01-28', 'end': '2025-02-04', 'days': 8}, {'start': '2025-02-08', 'end': '2025-02-09', 'days': 2}, {'start': '2025-02-15', 'end': '2025-02-16', 'days': 2}, {'start': '2025-02-22', 'end': '2025-02-23', 'days': 2}, {'start': '2025-03-01', 'end': '2025-03-02', 'days': 2}, {'start': '2025-03-08', 'end': '2025-03-09', 'days': 2}, {'start': '2025-03-15', 'end': '2025-03-16', 'days': 2}, {'start': '2025-03-22', 'end': '2025-03-23', 'days': 2}, {'start': '2025-03-29', 'end': '2025-03-30', 'days': 2}, {'start': '2025-04-04', 'end': '2025-04-06', 'days': 3}, {'start': '2025-04-12', 'end': '2025-04-13', 'days': 2}, {'start': '2025-04-19', 'end': '2025-04-20', 'days': 2}, {'start': '2025-04-26', 'end': '2025-04-27', 'days': 2}, {'start': '2025-05-01', 'end': '2025-05-05', 'days': 5}, {'start': '2025-05-10', 'end': '2025-05-11', 'days': 2}, {'start': '2025-05-17', 'end': '2025-05-18', 'days': 2}, {'start': '2025-05-24', 'end': '2025-05-25', 'days': 2}, {'start': '2025-05-31', 'end': '2025-06-02', 'days': 3}, {'start': '2025-06-07', 'end': '2025-06-08', 'days': 2}, {'start': '2025-06-14', 'end': '2025-06-15', 'days': 2}, {'start': '2025-06-21', 'end': '2025-06-22', 'days': 2}, {'start': '2025-06-28', 'end': '2025-06-29', 'days': 2}, {'start': '2025-07-05', 'end': '2025-07-06', 'days': 2}, {'start': '2025-07-12', 'end': '2025-07-13', 'days': 2}, {'start': '2025-07-19', 'end': '2025-07-20', 'days': 2}, {'start': '2025-07-26', 'end': '2025-07-27', 'days': 2}, {'start': '2025-08-02', 'end': '2025-08-03', 'days': 2}, {'start': '2025-08-09', 'end': '2025-08-10', 'days': 2}, {'start': '2025-08-16', 'end': '2025-08-17', 'days': 2}, {'start': '2025-08-23', 'end': '2025-08-24', 'days': 2}, {'start': '2025-08-30', 'end': '2025-08-31', 'days': 2}, {'start': '2025-09-06', 'end': '2025-09-07', 'days': 2}, {'start': '2025-09-13', 'end': '2025-09-14', 'days': 2}, {'start': '2025-09-20', 'end': '2025-09-21', 'days': 2}, {'start': '2025-09-27', 'end': '2025-09-28', 'days': 2}, {'start': '2025-10-01', 'end': '2025-10-08', 'days': 8}, {'start': '2025-10-11', 'end': '2025-10-12', 'days': 2}, {'start': '2025-10-18', 'end': '2025-10-19', 'days': 2}, {'start': '2025-10-25', 'end': '2025-10-26', 'days': 2}, {'start': '2025-11-01', 'end': '2025-11-02', 'days': 2}, {'start': '2025-11-08', 'end': '2025-11-09', 'days': 2}, {'start': '2025-11-15', 'end': '2025-11-16', 'days': 2}, {'start': '2025-11-22', 'end': '2025-11-23', 'days': 2}, {'start': '2025-11-29', 'end': '2025-11-30', 'days': 2}, {'start': '2025-12-06', 'end': '2025-12-07', 'days': 2}, {'start': '2025-12-13', 'end': '2025-12-14', 'days': 2}, {'start': '2025-12-20', 'end': '2025-12-21', 'days': 2}, {'start': '2025-12-27', 'end': '2025-12-28', 'days': 2}, {'start': '2026-01-01', 'end': '2026-01-04', 'days': 4}, {'start': '2026-01-10', 'end': '2026-01-11', 'days': 2}, {'start': '2026-01-17', 'end': '2026-01-18', 'days': 2}, {'start': '2026-01-24', 'end': '2026-01-25', 'days': 2}, {'start': '2026-01-31', 'end': '2026-02-01', 'days': 2}, {'start': '2026-02-07', 'end': '2026-02-08', 'days': 2}, {'start': '2026-02-14', 'end': '2026-02-23', 'days': 10}, {'start': '2026-02-28', 'end': '2026-03-01', 'days': 2}, {'start': '2026-03-07', 'end': '2026-03-08', 'days': 2}, {'start': '2026-03-14', 'end': '2026-03-15', 'days': 2}, {'start': '2026-03-21', 'end': '2026-03-22', 'days': 2}, {'start': '2026-03-28', 'end': '2026-03-29', 'days': 2}, {'start': '2026-04-04', 'end': '2026-04-06', 'days': 3}, {'start': '2026-04-11', 'end': '2026-04-12', 'days': 2}, {'start': '2026-04-18', 'end': '2026-04-19', 'days': 2}, {'start': '2026-04-25', 'end': '2026-04-26', 'days': 2}, {'start': '2026-05-01', 'end': '2026-05-05', 'days': 5}, {'start': '2026-05-09', 'end': '2026-05-10', 'days': 2}, {'start': '2026-05-16', 'end': '2026-05-17', 'days': 2}, {'start': '2026-05-23', 'end': '2026-05-24', 'days': 2}, {'start': '2026-05-30', 'end': '2026-05-31', 'days': 2}, {'start': '2026-06-06', 'end': '2026-06-07', 'days': 2}, {'start': '2026-06-13', 'end': '2026-06-14', 'days': 2}, {'start': '2026-06-19', 'end': '2026-06-21', 'days': 3}]

## Macro Composite History

- status: blocked
- source_table: None

## Position Holding History

- status: research_only
- position_count: 6
- symbol_count: 1
- snapshot_range: 2026-05-13 to 2026-06-22
- market_state_counts: {'UNKNOWN': 6}
- OVERHEAT sample count: 0

## Price Path Adjustment Coverage

- total_path_rows: 20259
- missing_adjustment_factor_rows: 3564
- missing_adjustment_factor_ratio: 0.175922
- affected_symbol_date_count: 3246
- top_missing_adjustment_factor_symbols: [{'stock_code': '000823.SZ', 'missing_rows': 36, 'first_date': '2024-11-14', 'last_date': '2025-01-24'}, {'stock_code': '300971.SZ', 'missing_rows': 36, 'first_date': '2025-03-21', 'last_date': '2025-04-24'}, {'stock_code': '600693.SH', 'missing_rows': 33, 'first_date': '2025-01-02', 'last_date': '2025-01-24'}, {'stock_code': '600530.SH', 'missing_rows': 25, 'first_date': '2025-01-02', 'last_date': '2025-06-26'}, {'stock_code': '002165.SZ', 'missing_rows': 24, 'first_date': '2025-04-01', 'last_date': '2025-04-24'}, {'stock_code': '603868.SH', 'missing_rows': 24, 'first_date': '2025-01-02', 'last_date': '2025-01-24'}, {'stock_code': '603893.SH', 'missing_rows': 24, 'first_date': '2025-01-02', 'last_date': '2025-01-24'}, {'stock_code': '002369.SZ', 'missing_rows': 23, 'first_date': '2025-01-02', 'last_date': '2025-01-24'}, {'stock_code': '601869.SH', 'missing_rows': 22, 'first_date': '2025-01-02', 'last_date': '2025-09-04'}, {'stock_code': '600121.SH', 'missing_rows': 21, 'first_date': '2025-10-28', 'last_date': '2025-11-21'}]

## Liquidity Thresholds

- daily_amount_unit_assumption: RMB from daily_amount; verify upstream field when all thresholds fail
- daily_amount_min: 26436.330000
- daily_amount_median: 678639.815000
- daily_amount_p90: 2931913.079000
- daily_amount_max: 17572905.892000

| threshold_rmb | pass_count | fail_count | missing_count | pass_ratio |
|---:|---:|---:|---:|---:|
| 20000000.000000 | 0 | 826 | 0 | 0.000000 |
| 50000000.000000 | 0 | 826 | 0 | 0.000000 |
| 100000000.000000 | 0 | 826 | 0 | 0.000000 |
| 200000000.000000 | 0 | 826 | 0 | 0.000000 |

## Conclusion

- blockers: ['gate exposure fallback ratio 34.22% is above 10%', 'macro composite history is missing or lacks required fields', 'liquidity thresholds have no passing known rows']
- research_flags: ['position holding history is sparse', 'some path rows use raw fallback because adjustment factors are missing']
