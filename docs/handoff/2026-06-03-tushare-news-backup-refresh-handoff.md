# Tushare News Backup Refresh Handoff

## Scope

This handoff covers the homepage `政策与资金面` news fallback closure:

- The page reads already landed news rows instead of implying automatic ingest.
- Choice landed source errors such as `error_code=10001012` are displayed as
  source status, not ordinary empty news.
- Tushare remains the backup source when usable landed rows exist.
- Operators get a trusted refresh entry point, dry-run profile, scheduler
  handoff template, and go-live checklist.

This handoff does not authorize database schema changes, auth/permission
framework changes, scheduler/cache base changes, public write route opening, or
homepage-triggered writes.

## Related Files

- `frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.ts`
- `frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.test.ts`
- `backend/app/tasks/choice_news.py`
- `scripts/refresh_tushare_news_backup.py`
- `tests/test_tushare_news_backup_refresh_script.py`
- `docs/tushare_news_backup_refresh_runbook.md`
- `docs/templates/tushare_news_backup_refresh_scheduler_handoff.md`
- `docs/templates/tushare_news_backup_refresh_go_live_checklist.md`
- `docs/MAINTENANCE.md`

## Operator Path

Use dry-run before any refresh:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

Dry-run must not call Tushare, must not call the actor, and must not write to
DuckDB. It reports `current_backup_state.status`, topic row counts,
`latest_received_at`, `error_rows`, and `blank_payload_rows`.

After credentials and dry-run evidence are accepted, a trusted operator may run
the sync command or enqueue `ingest_tushare_news_to_choice_news` through the
same script. Recurring enablement should use
`docs/templates/tushare_news_backup_refresh_scheduler_handoff.md` and must
complete `docs/templates/tushare_news_backup_refresh_go_live_checklist.md`
before the timer is enabled.

## Reserved Boundaries

These routes remain reserved and are not maintenance entry points:

- `POST /ui/news/tushare-npr/ingest`
- `POST /api/news/tushare-npr/ingest`

The homepage continues to read through `/ui/news/choice-events/latest`.

## Verification

Run from the repository root:

```powershell
python -m pytest tests/test_cleanup_dev_artifacts.py::test_maintenance_doc_records_cleanup_and_parallelism_boundaries tests/test_tushare_news_backup_refresh_script.py tests/test_tushare_news_backup_refresh_runbook.py tests/test_choice_news_routes.py::test_tushare_npr_ingest_ui_still_503_reserved tests/test_write_route_auth_contract.py tests/test_worker_bootstrap.py tests/test_tushare_news_ingest.py -q
```

Run from `frontend/`:

```powershell
npm run test -- macroNewsPresentation buildHomeMacroBriefingModel dashboardHomeView ResearchCalendarSection
npm run debt:audit
```

Latest verification in this thread:

- Backend/docs boundary target: `62 passed`
- Frontend target: `4 files / 41 tests passed`
- Frontend debt audit: passed with no growth over baseline

## Remaining Operations Work

- Configure a valid `MOSS_TUSHARE_TOKEN` in the target operator environment.
- Run real dry-run against the intended DuckDB file.
- Attach dry-run, first-run, post-run dry-run, and homepage evidence to the
  operations ticket or log bundle.
- Enable any external timer only after the go-live checklist is complete.

No real Tushare call, real ingest, production DuckDB write, commit, push, or PR
creation was performed as part of this handoff.
