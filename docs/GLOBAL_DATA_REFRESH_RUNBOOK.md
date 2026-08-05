# Global Core Data Refresh Runbook

## Canonical command

Run from the repository root with an explicit business date:

```powershell
.\.venv\Scripts\python.exe scripts\run_global_data_refresh.py --report-date 2026-07-31
```

Preview the exact plan without writes:

```powershell
.\.venv\Scripts\python.exe scripts\run_global_data_refresh.py --report-date 2026-07-31 --dry-run
```

An approved manual FX replay is explicit:

```powershell
.\.venv\Scripts\python.exe scripts\run_global_data_refresh.py `
  --report-date 2026-07-31 `
  --fx-source-path F:\approved-source\fx_daily_mid.csv
```

No date is inferred and no CSV is silently selected.

## Required order

1. Ingest and materialize `zqtz` / `tyw`, formal FX, and formal balance.
2. Materialize bond analytics.
3. Materialize the formal risk tensor.
4. Materialize formal PnL for the same report date.
5. Rebuild product-category PnL.
6. Refresh accounting asset movement.
7. Refresh scoped source previews.
8. Verify every required table at the requested date and verify formal FX completeness, canonical grain, positive rates, and lineage.

The command uses a global operator lock and stops at the first required failure.
Completed upstream steps are idempotent checkpoints; rerun the same command after
correcting the recorded failure. A failed receipt never reports the overall run
as completed.

## Success criteria

The process exits `0` only when all steps and final verification complete. The
JSON receipt includes the run ID, requested date, per-step result, elapsed time,
and final table/FX checks. Any required failure exits non-zero and identifies
`failed_step`, `error_type`, and `error_message`.

This entrypoint covers the governed core financial chain used by balance, bond,
risk, PnL, product-category, movement, and source-preview workflows. Independent
vendor-specific macro, news, and stock refreshes retain their own calendars and
SLAs and are not silently mixed into this report-date transaction.
