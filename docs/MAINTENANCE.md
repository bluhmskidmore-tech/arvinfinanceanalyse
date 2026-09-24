# MOSS-V3 Maintenance

This note records the current maintenance boundary for local development cleanup
and task parallelism. It does not authorize business metric, API, schema, cache,
or worker architecture changes.

## Interpreter

Every Python command below is written as `.\.venv\Scripts\python.exe` on purpose. A bare `python`
is regularly shadowed by an unrelated venv on developer machines, and several entries on this page
**write data** (materialize jobs, governance receipts, DuckDB refreshes). Running one of those under
the wrong interpreter is not a clean failure. POSIX equivalent: `.venv/bin/python`.

Read the flag before running anything here:

| Flag | Effect |
| --- | --- |
| `--dry-run` | Read-only. Prints the plan. Safe to run any time. |
| `--stage pre-enable` / `--stage post-enable` / preflight scripts | Read-only gates. Safe. |
| `--run-once` | **Writes**: executes the refresh synchronously against the configured DuckDB/governance paths. Single-writer window required. |
| `--enqueue` | **Writes**: hands the job to the Dramatiq worker, which then writes. |

The `--run-once` and `--enqueue` commands below are documented for path/flag shape. Do not run them
casually: they need an agreed single-writer window and must not overlap another DuckDB writer.

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

Known local disposable roots are the only exception:

- old `.codex-tmp/pytest-*`
- `.pytest-basetemp`
- `test_output/accounting_asset_movement`
- `test_output/formal_balance_pipeline`
- `frontend/test-results`
- `.mypy_cache`
- `backend/.mypy_cache`

These remain eligible for cleanup even when they contain DuckDB/CSV/SQLite
artifacts. This is a narrow path whitelist for known generated verification
outputs and rebuildable type-check caches, not a global relaxation for data
files. Unknown `test_output/*` subtrees are not disposable by default.

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
`.\.venv\Scripts\python.exe scripts/refresh_tushare_news_backup.py --dry-run` before any trusted operator
refresh. The reserved ingest routes remain reserved and are not maintenance
entry points. Before enabling any recurring timer, run the read-only
`.\.venv\Scripts\python.exe scripts/tushare_news_backup_timer_preflight.py --stage all` to review both
pre-enable and post-enable gates in one report. Use
`.\.venv\Scripts\python.exe scripts/tushare_news_backup_timer_preflight.py --stage all --format markdown`
when the operator handoff needs Markdown text, or
`.\.venv\Scripts\python.exe scripts/tushare_news_backup_timer_preflight.py --stage all --format ops-gap`
when operations needs the external input gap packet. A
`blocked` verdict means an owner, scheduler, write-window, rollback, page
evidence, or enablement-packet gate is still open. Use
`.\.venv\Scripts\python.exe scripts/tushare_news_backup_timer_preflight.py --stage pre-enable` before
creating the timer. After the first scheduled run, use
`.\.venv\Scripts\python.exe scripts/tushare_news_backup_timer_preflight.py --stage post-enable` to also
require the timer evidence fields.

### Homepage macro release source refresh

The homepage release-context refresh is a schedulable operator workflow. It
refreshes CPI/PPI/GDP through the governed Tushare macro ingest and limits the
PMI overlap refresh to the actual `tushare_macro` vendor. It does not relabel
or replace existing NBS evidence.

- Safe plan (read-only): `.\.venv\Scripts\python.exe scripts/home_macro_release_refresh.py --dry-run`
- Approved synchronous validation (**writes**): `.\.venv\Scripts\python.exe scripts/home_macro_release_refresh.py --run-once`
- External timer target (**writes** via worker): `.\.venv\Scripts\python.exe scripts/home_macro_release_refresh.py --enqueue`
- Fail-closed gate (read-only): `.\.venv\Scripts\python.exe scripts/home_macro_release_refresh_timer_preflight.py`
- Scheduler handoff: `docs/templates/home_macro_release_refresh_scheduler_handoff.md`
- Go-live checklist: `docs/templates/home_macro_release_refresh_go_live_checklist.md`
- Enablement packet: `docs/templates/home_macro_release_refresh_timer_enablement_packet.md`

The repository does not install or enable the timer. Operations must name the
owner, host, single-writer window, log path, and rollback procedure, then attach
approved run-once and first-scheduled-run evidence. Until then the preflight
returns a nonzero, `blocked` result by design.

### Macro toolkit freshness refresh

Keeps macro-toolkit observation inputs current (commodity bars, CSI/public
cross-asset headlines, Choice EMM00088132 policy rate, NCD.SHIBOR proxy, and
CFFEX member rank). Sequential single-writer pipeline (`macro_toolkit_freshness_refresh_v3`); CFFEX soft-fails
on weekend/vendor gaps.

- Safe plan (read-only): `.\.venv\Scripts\python.exe scripts/macro_toolkit_freshness_refresh.py --dry-run`
- Shadow validation (**writes** a shadow receipt): `.\.venv\Scripts\python.exe scripts/macro_toolkit_freshness_refresh.py --run-once --run-kind shadow --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.shadow.json`
- Local timer target, no worker (**writes**): `.\.venv\Scripts\python.exe scripts/macro_toolkit_freshness_refresh.py --run-once --run-kind scheduled --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json`
- Production timer target, with worker (**writes**): `.\.venv\Scripts\python.exe scripts/macro_toolkit_freshness_refresh.py --enqueue --run-kind scheduled --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json`
- Pre-enable gate (read-only): `.\.venv\Scripts\python.exe scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage pre-enable`
- Post-enable gate (read-only): `.\.venv\Scripts\python.exe scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage post-enable --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json`
- Scheduler handoff: `docs/templates/macro_toolkit_freshness_refresh_scheduler_handoff.md`
- Go-live checklist: `docs/templates/macro_toolkit_freshness_refresh_go_live_checklist.md`
- Enablement packet: `docs/templates/macro_toolkit_freshness_refresh_timer_enablement_packet.md`
- Optional local Windows installer: `scripts/install_macro_toolkit_freshness_timer.ps1`

Recommended window: daily `18:30` `Asia/Shanghai` (UTC-4 host-local `06:30`).
Do not overlap other DuckDB writers. Post-enable requires a completed
`--run-once --run-kind scheduled` receipt; enqueue acknowledgements and shadow
receipts are not valid first-run proof (the Dramatiq actor does not yet persist a
completed receipt). The enablement packet does not embed scheduler create commands.
