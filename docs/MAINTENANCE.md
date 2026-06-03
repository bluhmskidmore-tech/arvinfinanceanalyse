# MOSS-V3 Maintenance

This note records the current maintenance boundary for local development cleanup
and task parallelism. It does not authorize business metric, API, schema, cache,
or worker architecture changes.

## Development Artifact Cleanup

Use `scripts/cleanup-dev-artifacts.ps1` from the repository root.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cleanup-dev-artifacts.ps1
```

The default mode is a dry-run. It lists old development artifacts and deletes
nothing. Pass `-Apply` only after reviewing the candidate list.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cleanup-dev-artifacts.ps1 -Apply
```

Default cleanup keeps the most recent 7 days and targets local verification
artifacts such as `.codex-tmp/pytest-*`, `.pytest-tmp*`, pytest/ruff/mypy
caches, `__pycache__`, `test_output`, `frontend/test-results`, and old root or
frontend `.log` files. Screenshot `.png` files are not included by default; use
`-IncludeScreenshots` to include old root and frontend screenshots with a
14-day retention window.

The cleanup script protects business inputs and evidence. It must not remove
`data/`, `data_input/`, `tmp-governance/`, `.git/`, `.omx/`, `.gitnexus/`,
`.venv/`, `node_modules/`, or candidate directories that contain DuckDB, CSV,
Parquet, Excel, SQLite, WAL, pickle, or governance JSONL files.

## Parallelism Boundary

Do not raise the default `MOSS_DEV_WORKER_PROCESSES` value from 1 as a broad
optimization. Keep the existing rule that DuckDB writes flow through
`backend/app/tasks/`; API and service paths remain read-oriented for business
surfaces.

Safe parallel lanes:

- Read-only checks and static audits.
- Frontend tests and type checks.
- Network/vendor fetches that do not write the same fact table or cache
  identity.
- Non-writing preview and diagnostics.

Serial or explicitly locked lanes:

- Formal materialize jobs.
- DuckDB writes.
- `cache_manifest` and cache-version publication.
- Lineage and governance writes.

Future throughput work should use queue separation instead of global worker
expansion: a `read/vendor queue` may scale out, while the
`materialize/write queue` stays single-writer or uses an explicit write lock.

## Operator Runbooks

Tushare news backup refresh for the homepage policy/funding card is documented
as an operator workflow, not a homepage write path:

- Runbook: `docs/tushare_news_backup_refresh_runbook.md`
- Scheduler handoff template:
  `docs/templates/tushare_news_backup_refresh_scheduler_handoff.md`
- Go-live checklist:
  `docs/templates/tushare_news_backup_refresh_go_live_checklist.md`
- Timer enablement packet:
  `docs/templates/tushare_news_backup_timer_enablement_packet.md`

Keep the homepage read-only on `/ui/news/choice-events/latest`; use
`scripts/refresh_tushare_news_backup.py --dry-run` before any trusted operator
refresh. The reserved ingest routes remain reserved and are not maintenance
entry points. Before enabling any recurring timer, run the read-only
`scripts/tushare_news_backup_timer_preflight.py --stage all` to review both
pre-enable and post-enable gates in one report. Use
`scripts/tushare_news_backup_timer_preflight.py --stage all --format markdown`
when the operator handoff needs Markdown text. A
`blocked` verdict means an owner, scheduler, write-window, rollback, page
evidence, or enablement-packet gate is still open. Use
`scripts/tushare_news_backup_timer_preflight.py --stage pre-enable` before
creating the timer. After the first scheduled run, use
`scripts/tushare_news_backup_timer_preflight.py --stage post-enable` to also
require the timer evidence fields.
