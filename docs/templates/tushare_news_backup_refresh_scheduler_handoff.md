# Tushare News Backup Refresh Scheduler Handoff

Use this template when operations decides to run the Tushare news backup refresh
on a timer. It is a handoff checklist, not a scheduler implementation.

## Ownership

- Business surface: homepage `政策与资金面` card.
- Read API: `/ui/news/choice-events/latest`.
- Operator entry point: `scripts/refresh_tushare_news_backup.py`.
- Background actor: `ingest_tushare_news_to_choice_news`.
- Credential owner: `<team/person>`.
- Schedule owner: `<team/person>`.

## Boundaries

- Do not schedule the homepage.
- Do not add a homepage auto-ingest button or page-triggered write.
- Do not open `POST /ui/news/tushare-npr/ingest`.
- Do not open `POST /api/news/tushare-npr/ingest`.
- Do not change database schema, auth/permission framework, scheduler base,
  cache base, or global SDK wrappers for this handoff.
- Keep DuckDB refresh as a single writer job or use an approved write lock.

## Preconditions

- `MOSS_TUSHARE_TOKEN` is present in the scheduled job environment.
- The scheduled job points at the intended DuckDB path.
- The job runs from the repository root or sets the repository root as its
  working directory.
- The refresh window avoids other DuckDB write/materialization jobs.
- Alerting/log retention is owned outside the homepage.

## Preflight

Run dry-run manually before enabling the timer:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

After the go-live checklist and evidence bundle are filled, run the read-only
timer preflight before enabling the external timer:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable
```

For the operator-readable go/no-go status, run:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable --format markdown
```

To review both pre-enable and post-enable gates in one read-only bundle, run:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all
```

For operator handoff Markdown, run:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all --format markdown
```

For the external operations input gap packet, run:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all --format ops-gap
```

Do not enable the timer while this preflight returns `blocked`.

Acceptance:

- `status` is `dry_run`.
- `current_backup_state.status` is `available`.
- Existing `error_rows` and `blank_payload_rows` are understood before refresh.

## Example Windows Task Scheduler Command

Use `docs/templates/tushare_news_backup_timer_enablement_packet.md` for the
fillable host, Python executable, log path, refresh window, and rollback fields.
This handoff gives command shape only; the packet records the actual operations
values.

Program:

```text
powershell.exe
```

Arguments:

```text
-NoProfile -ExecutionPolicy Bypass -Command "Set-Location 'F:\MOSS-V3'; python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina"
```

Use the non-`--enqueue` form when the scheduled host itself is the trusted
operator runner.

## Example Worker Queue Command

Use this only when the worker is already managed separately:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --enqueue
```

Acceptance:

- `status` is `queued`.
- `actor` is `ingest_tushare_news_to_choice_news`.
- Worker logs show the actor completed.

## Example Cron Command

```cron
15 8 * * 1-5 cd /srv/MOSS-V3 && /usr/bin/python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina >> /var/log/moss/tushare-news-backup-refresh.log 2>&1
```

Adjust time, path, Python binary, and log location for the deployment host.

## Post-Run Validation

After the timer fires, run:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable
```

Accept the scheduled run only when:

- `current_backup_state.status` is `available`.
- `tushare.news.sina` and/or `tushare.major_news` has a recent
  `latest_received_at`.
- `error_rows` is `0` for topics the homepage should use.
- `blank_payload_rows` is `0` for topics the homepage should use.
- Homepage still reads via `/ui/news/choice-events/latest`.

## Rollback

- Disable the external timer.
- Leave landed rows in DuckDB unless a separate data-quality decision requires
  cleanup.
- Keep the reserved routes reserved.
- Re-run dry-run and page verification after rollback.
