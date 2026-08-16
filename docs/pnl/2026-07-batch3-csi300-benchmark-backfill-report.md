# 2026-07 Batch 3 CSI300 Benchmark Backfill Report

- status: completed
- duckdb_path: F:\MOSS-V3\data\moss.duckdb
- target_backup_before_write: F:\MOSS-V3\data\moss.pre-csi300-followup-20260705.duckdb
- target_backup_size_bytes: 1082929152
- target_backup_created_at: 2026-07-05T07:39:42
- target_backup_last_write_time: 2026-07-05T04:18:22
- target_backup_sha256: 5F3E6F589534CE9BE23F1A3327F46D41B81E41F28D4C5F6EA7FDB015BF16D355
- source_backup_duckdb_path: F:\MOSS-V3\data\moss.pre-stock-refresh-20260618T171201.duckdb
- source_table: fact_choice_macro_daily
- series_id: CA.CSI300
- inserted_count: 306
- inserted_min_date: 2024-09-25
- inserted_max_date: 2025-12-29
- conflict_count: 0
- live_strategy_changes: none

## Command

```powershell
python scripts/backfill_csi300_benchmark_from_backup.py --duckdb-path F:\MOSS-V3\data\moss.duckdb --backup-duckdb-path F:\MOSS-V3\data\moss.pre-stock-refresh-20260618T171201.duckdb --start-date 2024-09-25 --end-date 2026-06-23 --governance-dir F:\MOSS-V3\data\governance
```

## Before / After

| metric | before | after |
|---|---:|---:|
| CA.CSI300 rows in execution window | 113 | 419 |
| calendar replayed rows | 113 | 419 |
| calendar fallback rows | 524 | 218 |
| calendar fallback ratio | 0.822606 | 0.342229 |
| trading-day fallback ratio | 0.774869 | 0.000000 |

## Interpretation

The benchmark backfill repaired the portfolio trading-day exposure path: all 382 portfolio equity-curve dates now use per-date replayed exposure rather than policy state fallback.

The calendar-day readiness report remains blocked because it counts non-trading days in the natural-date execution window. Those dates still have no benchmark observation and are not force-filled in this research package.
