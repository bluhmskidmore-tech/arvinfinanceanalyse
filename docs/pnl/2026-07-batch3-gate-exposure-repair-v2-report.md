# 2026-07 Batch 3 Gate Exposure Repair V2 Report

- status: blocked
- repair_result: partially_repaired; trading-day exposure fallback is below 10%, calendar-day coverage still misses non-trading days
- date_window: {'start': '2024-09-25', 'end': '2026-06-23'}

## Coverage

| basis | date_count | actual_or_replayed | fallback_rows | fallback_ratio |
|---|---:|---:|---:|---:|
| calendar | 637 | 419 | 218 | 0.342229 |
| trading-day equity | 382 | 382 | 0 | 0.000000 |

## Persisted Exposure Tables

| table | exists | status | rows | window_non_null_exposure_rows | first | last |
|---|---|---|---:|---:|---|---|
| livermore_monitor_append | False | missing | None | None | None | None |
| livermore_gate_history | False | missing | None | None | None | None |
| livermore_gate_supplement | False | missing | None | None | None | None |

## Candidate Evidence And Replay Sources

{"consistent_gate_dates": 0, "dates_with_gate_evidence": 0, "exists": true, "inconsistent_dates_sample": [], "inconsistent_gate_dates": 0, "raw_evidence_rows": 5493, "table": "livermore_candidate_history"}

{"choice_market_snapshot": {"columns": ["frequency", "rule_version", "run_id", "series_id", "series_name", "source_version", "trade_date", "unit", "value_numeric", "vendor_name", "vendor_series_code", "vendor_version"], "date_col": "trade_date", "exists": true, "window_first_date": null, "window_last_date": null, "window_rows": 0}, "fact_choice_macro_daily": {"columns": ["frequency", "quality_flag", "rule_version", "run_id", "series_id", "series_name", "source_version", "trade_date", "unit", "value_numeric", "vendor_version"], "date_col": "trade_date", "exists": true, "window_first_date": "2024-09-25", "window_last_date": "2026-06-23", "window_rows": 419}, "fact_livermore_gate_supplement_daily": {"columns": ["breadth_5d", "limit_up_quality_ok", "rule_version", "run_id", "source_version", "trade_date", "vendor_version"], "date_col": "trade_date", "exists": true, "mapping_assessment": {"exposure_fields": [], "reason": "supplement table has rows but lacks an explicit exposure field; it cannot be treated as persisted market_gate.exposure without replaying the benchmark/gate calculation", "state_fields": [], "supplement_only_fields": ["breadth_5d", "limit_up_quality_ok"], "usable_as_exposure_history": false}, "window_first_date": "2024-09-25", "window_last_date": "2026-06-22", "window_rows": 418}}

## Blockers

- calendar-day gate exposure fallback ratio remains above 10%

Stop condition: this remains no-go until both calendar and trading-day fallback ratios are below 10%.
