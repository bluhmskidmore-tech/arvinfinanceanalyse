# Tushare News Backup Refresh Runbook

## Purpose

This runbook refreshes the landed Tushare news backup used by the dashboard
policy/funding news card when Choice news is unavailable or returns source
errors such as `error_code=10001012`.

The homepage remains read-only. It calls `/ui/news/choice-events/latest` and
reads already landed rows. This runbook does not change the database schema,
permission framework, scheduler, cache base, or public API/UI write surfaces.

## Scope

Covered:

- Inspect current landed Tushare backup state without writing.
- Run a trusted operator refresh from the local script.
- Enqueue the background actor when a worker is already running.
- Verify the page fallback after rows land.

Not covered:

- Restoring Choice account permission.
- Opening `/ui/news/tushare-npr/ingest` or `/api/news/tushare-npr/ingest`.
- Scheduling policy or queue platform changes.
- Running development-time real ingest unless an operator intentionally runs the
  non-`--dry-run` command with valid Tushare credentials.

## Preconditions

- `MOSS_TUSHARE_TOKEN` is configured in the operator environment or app
  settings.
- `duckdb_path` points to the target MOSS DuckDB file, for example
  `data/moss.duckdb`.
- For `--enqueue`, the worker process is running and has the
  `ingest_tushare_news_to_choice_news` actor loaded.
- For synchronous refresh, the DuckDB file is not locked by another write.

## Dry Run

Use dry-run before any refresh:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

Dry-run does not call Tushare, does not call the actor, and does not write to
DuckDB. It only prints the current backup profile.

Read the output:

- `status`: should be `dry_run`.
- `would_call`: shows the exact arguments that a real refresh would use.
- `current_backup_state.status`:
  - `available`: `choice_news_event` exists and Tushare backup topics were
    inspected.
  - `missing_database`: the configured DuckDB file does not exist.
  - `missing_table`: DuckDB exists but `choice_news_event` is absent.
- `current_backup_state.topics[*].topic_code`: expected backup topics are
  `tushare.major_news`, `tushare.news.sina`, and `tushare.npr`.
- `rows`: current landed row count for that topic.
- `latest_received_at`: latest landed timestamp; this should move after a
  successful refresh for active sources.
- `error_rows`: should stay `0` for usable backup rows.
- `blank_payload_rows`: should stay `0`; nonzero means the page may still have
  no displayable headline.

## Synchronous Refresh

After dry-run looks correct and credentials are available, run the operator
refresh:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina
```

The script calls `ingest_tushare_news_to_choice_news.fn(...)` locally. This is a
trusted ops entry point, not a UI action.

Useful narrowing options:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --news-limit 100 --limit 20 --major-lookback-hours 48 --news-lookback-hours 48
```

## Enqueue Refresh

Use enqueue only when the background worker is already running:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --enqueue
```

Expected output:

- `status` is `queued`.
- `actor` is `ingest_tushare_news_to_choice_news`.
- `message_id` is present when the queue returns one.

Then check worker logs and rerun dry-run to verify landed rows.

## Scheduling Handoff

If operations wants a recurring refresh, use
`docs/templates/tushare_news_backup_refresh_scheduler_handoff.md` as the
handoff checklist.

The timer should run this script or enqueue the same actor from trusted
operations automation. It must not schedule the homepage, open the reserved
ingest routes, or change scheduler/cache/auth/database base layers as part of
this page closure.

Before enabling a recurring timer, complete
`docs/templates/tushare_news_backup_refresh_go_live_checklist.md` and attach the
dry-run, first-run, post-run dry-run, and homepage evidence to the operations
ticket or log bundle.

## Post-Refresh Validation

Run dry-run again:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

Accept the refresh only when:

- `current_backup_state.status` is `available`.
- `tushare.news.sina` and/or `tushare.major_news` has a recent
  `latest_received_at`.
- `error_rows` is `0` for the topics the page should use.
- `blank_payload_rows` is `0` for the topics the page should use.
- Row counts did not unexpectedly drop to zero.

Then open the homepage and check the `政策与资金面` card:

- It should read landed data, not claim automatic ingest.
- If Choice still returns `10001012`, the page may show Choice permission status
  only after usable Tushare fallback is unavailable.
- When Tushare backup headlines match policy/funding keywords, the page should
  show the Tushare fallback instead of an empty Choice permission state.
- If only broader macro Tushare headlines match, the page can show
  `来源状态：Tushare 宏观兜底（非严格资金面）`.

## Reserved Surfaces

These routes stay reserved and must continue to return reserved/503 behavior:

- `POST /ui/news/tushare-npr/ingest`
- `POST /api/news/tushare-npr/ingest`

Do not use the homepage, UI buttons, or these reserved routes to refresh news.
Use this operator script or trusted scheduling around the same actor.

## Failure Modes

| Symptom | Likely cause | Action |
| --- | --- | --- |
| `MOSS_TUSHARE_TOKEN` error | Missing Tushare credential | Configure the token in the operator environment/settings and retry dry-run first, then refresh. |
| Tushare permission/API error | Token lacks the required Tushare endpoint permission or quota | Escalate credential entitlement; do not change page logic or reserved routes. |
| DuckDB lock/write failure | Another writer holds the target database | Stop the competing write or retry after it finishes. |
| `status=queued` but rows do not move | Worker not running, actor not loaded, or queue failure | Check worker status/logs for `ingest_tushare_news_to_choice_news`, then rerun dry-run. |
| `tushare.npr` stays stale | Policy repository source may update less frequently than news/major feeds | Prefer `tushare.news.sina` and `tushare.major_news` freshness for the homepage fallback; treat stale `npr` as a source limitation unless policy rows are required. |
| `blank_payload_rows` is nonzero | Landed rows have no displayable headline text | Inspect ingest output and source payload before accepting the refresh. |
| Homepage still shows Choice permission status | No usable Tushare policy/funding or macro fallback headline was landed | Verify dry-run topics, refresh result, and page keyword matching before changing frontend behavior. |

## Targeted Checks

After changing this runbook or the refresh script, run:

```powershell
python -m pytest tests/test_tushare_news_backup_refresh_script.py tests/test_tushare_news_backup_refresh_runbook.py tests/test_choice_news_routes.py::test_tushare_npr_ingest_ui_still_503_reserved tests/test_write_route_auth_contract.py tests/test_worker_bootstrap.py -q
```

If frontend fallback presentation changes too, also run:

```powershell
cd frontend
npm run test -- macroNewsPresentation buildHomeMacroBriefingModel dashboardHomeView ResearchCalendarSection
npm run debt:audit
```
