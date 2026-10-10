# 2026-07 Batch 3 Gate Exposure Repair V3 Report

- status: ready
- repair_result: trading_day_repaired_calendar_pipeline_warning
- date_window: {'start': '2024-09-25', 'end': '2026-06-23'}
- calendar_gate_fallback_ratio: 0.342229
- trading_day_gate_fallback_ratio: 0.000000
- true_trading_day_missing_count: 0
- true_trading_day_missing_ratio: 0.000000
- calendar_missing_classification: non_trading_dates_only

## Calendar vs Trading-Day Coverage

| basis | date_count | actual_or_replayed | fallback_rows | fallback_ratio |
|---|---:|---:|---:|---:|
| calendar natural days | 637 | 419 | 218 | 0.342229 |
| trading-day equity curve | 382 | 382 | 0 | 0.000000 |
| benchmark trading calendar | 419 | 419 | 0 | 0.000000 |

## Calendar Missing Classification

- calendar_missing_total: 218
- calendar_missing_not_trading_day_count: 218
- calendar_missing_weekend_count: 182
- calendar_missing_weekday_non_trading_count: 36
- true_trading_day_missing_ranges: []
- calendar_missing_not_trading_day_ranges: [{'start': '2024-09-28', 'end': '2024-09-29', 'days': 2}, {'start': '2024-10-01', 'end': '2024-10-07', 'days': 7}, {'start': '2024-10-12', 'end': '2024-10-13', 'days': 2}, {'start': '2024-10-19', 'end': '2024-10-20', 'days': 2}, {'start': '2024-10-26', 'end': '2024-10-27', 'days': 2}, {'start': '2024-11-02', 'end': '2024-11-03', 'days': 2}, {'start': '2024-11-09', 'end': '2024-11-10', 'days': 2}, {'start': '2024-11-16', 'end': '2024-11-17', 'days': 2}, {'start': '2024-11-23', 'end': '2024-11-24', 'days': 2}, {'start': '2024-11-30', 'end': '2024-12-01', 'days': 2}, {'start': '2024-12-07', 'end': '2024-12-08', 'days': 2}, {'start': '2024-12-14', 'end': '2024-12-15', 'days': 2}, {'start': '2024-12-21', 'end': '2024-12-22', 'days': 2}, {'start': '2024-12-28', 'end': '2024-12-29', 'days': 2}, {'start': '2025-01-01', 'end': '2025-01-01', 'days': 1}, {'start': '2025-01-04', 'end': '2025-01-05', 'days': 2}, {'start': '2025-01-11', 'end': '2025-01-12', 'days': 2}, {'start': '2025-01-18', 'end': '2025-01-19', 'days': 2}, {'start': '2025-01-25', 'end': '2025-01-26', 'days': 2}, {'start': '2025-01-28', 'end': '2025-02-04', 'days': 8}, {'start': '2025-02-08', 'end': '2025-02-09', 'days': 2}, {'start': '2025-02-15', 'end': '2025-02-16', 'days': 2}, {'start': '2025-02-22', 'end': '2025-02-23', 'days': 2}, {'start': '2025-03-01', 'end': '2025-03-02', 'days': 2}, {'start': '2025-03-08', 'end': '2025-03-09', 'days': 2}, {'start': '2025-03-15', 'end': '2025-03-16', 'days': 2}, {'start': '2025-03-22', 'end': '2025-03-23', 'days': 2}, {'start': '2025-03-29', 'end': '2025-03-30', 'days': 2}, {'start': '2025-04-04', 'end': '2025-04-06', 'days': 3}, {'start': '2025-04-12', 'end': '2025-04-13', 'days': 2}, {'start': '2025-04-19', 'end': '2025-04-20', 'days': 2}, {'start': '2025-04-26', 'end': '2025-04-27', 'days': 2}, {'start': '2025-05-01', 'end': '2025-05-05', 'days': 5}, {'start': '2025-05-10', 'end': '2025-05-11', 'days': 2}, {'start': '2025-05-17', 'end': '2025-05-18', 'days': 2}, {'start': '2025-05-24', 'end': '2025-05-25', 'days': 2}, {'start': '2025-05-31', 'end': '2025-06-02', 'days': 3}, {'start': '2025-06-07', 'end': '2025-06-08', 'days': 2}, {'start': '2025-06-14', 'end': '2025-06-15', 'days': 2}, {'start': '2025-06-21', 'end': '2025-06-22', 'days': 2}, {'start': '2025-06-28', 'end': '2025-06-29', 'days': 2}, {'start': '2025-07-05', 'end': '2025-07-06', 'days': 2}, {'start': '2025-07-12', 'end': '2025-07-13', 'days': 2}, {'start': '2025-07-19', 'end': '2025-07-20', 'days': 2}, {'start': '2025-07-26', 'end': '2025-07-27', 'days': 2}, {'start': '2025-08-02', 'end': '2025-08-03', 'days': 2}, {'start': '2025-08-09', 'end': '2025-08-10', 'days': 2}, {'start': '2025-08-16', 'end': '2025-08-17', 'days': 2}, {'start': '2025-08-23', 'end': '2025-08-24', 'days': 2}, {'start': '2025-08-30', 'end': '2025-08-31', 'days': 2}, {'start': '2025-09-06', 'end': '2025-09-07', 'days': 2}, {'start': '2025-09-13', 'end': '2025-09-14', 'days': 2}, {'start': '2025-09-20', 'end': '2025-09-21', 'days': 2}, {'start': '2025-09-27', 'end': '2025-09-28', 'days': 2}, {'start': '2025-10-01', 'end': '2025-10-08', 'days': 8}, {'start': '2025-10-11', 'end': '2025-10-12', 'days': 2}, {'start': '2025-10-18', 'end': '2025-10-19', 'days': 2}, {'start': '2025-10-25', 'end': '2025-10-26', 'days': 2}, {'start': '2025-11-01', 'end': '2025-11-02', 'days': 2}, {'start': '2025-11-08', 'end': '2025-11-09', 'days': 2}, {'start': '2025-11-15', 'end': '2025-11-16', 'days': 2}, {'start': '2025-11-22', 'end': '2025-11-23', 'days': 2}, {'start': '2025-11-29', 'end': '2025-11-30', 'days': 2}, {'start': '2025-12-06', 'end': '2025-12-07', 'days': 2}, {'start': '2025-12-13', 'end': '2025-12-14', 'days': 2}, {'start': '2025-12-20', 'end': '2025-12-21', 'days': 2}, {'start': '2025-12-27', 'end': '2025-12-28', 'days': 2}, {'start': '2026-01-01', 'end': '2026-01-04', 'days': 4}, {'start': '2026-01-10', 'end': '2026-01-11', 'days': 2}, {'start': '2026-01-17', 'end': '2026-01-18', 'days': 2}, {'start': '2026-01-24', 'end': '2026-01-25', 'days': 2}, {'start': '2026-01-31', 'end': '2026-02-01', 'days': 2}, {'start': '2026-02-07', 'end': '2026-02-08', 'days': 2}, {'start': '2026-02-14', 'end': '2026-02-23', 'days': 10}, {'start': '2026-02-28', 'end': '2026-03-01', 'days': 2}, {'start': '2026-03-07', 'end': '2026-03-08', 'days': 2}, {'start': '2026-03-14', 'end': '2026-03-15', 'days': 2}, {'start': '2026-03-21', 'end': '2026-03-22', 'days': 2}, {'start': '2026-03-28', 'end': '2026-03-29', 'days': 2}, {'start': '2026-04-04', 'end': '2026-04-06', 'days': 3}, {'start': '2026-04-11', 'end': '2026-04-12', 'days': 2}, {'start': '2026-04-18', 'end': '2026-04-19', 'days': 2}, {'start': '2026-04-25', 'end': '2026-04-26', 'days': 2}, {'start': '2026-05-01', 'end': '2026-05-05', 'days': 5}, {'start': '2026-05-09', 'end': '2026-05-10', 'days': 2}, {'start': '2026-05-16', 'end': '2026-05-17', 'days': 2}, {'start': '2026-05-23', 'end': '2026-05-24', 'days': 2}, {'start': '2026-05-30', 'end': '2026-05-31', 'days': 2}, {'start': '2026-06-06', 'end': '2026-06-07', 'days': 2}, {'start': '2026-06-13', 'end': '2026-06-14', 'days': 2}, {'start': '2026-06-19', 'end': '2026-06-21', 'days': 3}]
- calendar_source_warning: Uses local CA.CSI300 benchmark observations as the A-share trading-day set; this validates strategy gate coverage but is not an independent exchange calendar.

## Replayed Exposure Lineage

{"benchmark_series_id": "CA.CSI300", "exposure_formula": "passed_conditions / 4", "gate_formula": "backend.app.core_finance.livermore_strategy.evaluate_market_gate", "source_tables": ["fact_choice_macro_daily"], "supplement_table": "fact_livermore_gate_supplement_daily"}

## Trading-Day Sources

| table | status | series_id | rows | first | last | source_versions | vendor_versions | rule_versions |
|---|---|---|---:|---|---|---|---|---|
| fact_choice_macro_daily | ready | CA.CSI300 | 419 | 2024-09-25 | 2026-06-23 | [{"value": "sv_tushare_index_daily_d98b61dd0c1d", "count": 306}, {"value": "sv_tushare_index_daily_61bfe54e9e84", "count": 113}] | [{"value": "vv_tushare_index_daily_000300SH_20260613", "count": 306}, {"value": "vv_tushare_index_daily_000300SH_20260628", "count": 113}] | [{"value": "rv_cross_asset_macro_environment_backfill_v1", "count": 306}, {"value": "rv_public_cross_asset_headline_v1", "count": 113}] |
| choice_market_snapshot | empty | CA.CSI300 | 0 | None | None | [] | [] | [] |

## Persisted Exposure Tables

| table | exists | status | rows | window_non_null_exposure_rows | first | last |
|---|---|---|---:|---:|---|---|
| livermore_monitor_append | False | missing | None | None | None | None |
| livermore_gate_history | False | missing | None | None | None | None |
| livermore_gate_supplement | False | missing | None | None | None | None |

## Warnings

- calendar-day fallback remains a pipeline coverage warning, not a strategy hard blocker

## Blockers

- none

Stop condition: strategy gate is blocked only when trading-day fallback exceeds 10%, true trading-day missing dates remain, or no trading-day validation source exists. Natural calendar gaps that validate as non-trading dates are pipeline warnings.
