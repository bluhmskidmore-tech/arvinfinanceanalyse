# Tushare News Backup Timer Enablement Packet

This packet does not enable the timer. It is an operations fill-in packet for
the recurring Tushare news backup refresh after the go-live checklist and
preflight are complete.

Use `docs/handoff/2026-06-03-tushare-news-backup-timer-ops-gap-packet.md` to
track the external owner, host, runtime, sign-off, and evidence inputs that must
be filled before this packet can pass preflight.

## Ownership And Runtime

- Credential owner: `<team/person>`
- Schedule owner: `<team/person>`
- Page acceptance owner: `<team/person>`
- Rollback owner: `<team/person>`
- Timer host: `<hostname>`
- Repository root: `<absolute repo path>`
- Python executable: `<absolute python path>`
- DuckDB path: `data/moss.duckdb`
- Log path: `<absolute log path>`
- Refresh window: `<local time and timezone>`
- Write-window exclusion note: `<how this avoids other DuckDB writes>`
- Alert/log retention owner: `<team/person>`

## Boundaries

- Homepage read API remains `/ui/news/choice-events/latest`.
- Do not schedule the homepage.
- Do not add a page-triggered refresh button.
- Do not open `POST /ui/news/tushare-npr/ingest`.
- Do not open `POST /api/news/tushare-npr/ingest`.
- Do not change database schema, auth/permission framework, scheduler base,
  cache base, or global SDK wrappers.
- Keep the refresh as a single DuckDB writer job or use an approved write lock.

## Command Drafts

Windows Task Scheduler command draft:

```text
Program:
<absolute python path>

Arguments:
scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina

Start in:
<absolute repo path>
```

Cron command draft:

```cron
<minute> <hour> * * 1-5 cd <absolute repo path> && <absolute python path> scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina >> <absolute log path> 2>&1
```

No `schtasks /Create` command is provided here.
No `crontab` install command is provided here.

## Verification Sequence

Run before enablement:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable
```

For the operator-readable go/no-go status:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable --format markdown
```

For the current pre-enable operations gaps:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable --format ops-gap
```

For a combined read-only review of both pre-enable and post-enable gates:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all
```

For operator handoff Markdown:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all --format markdown
```

For the external operations gap packet:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all --format ops-gap
```

The preflight must return `pass` before enablement. A `blocked` verdict with
`timer_enablement_packet_filled` means this packet still has placeholder owner,
host, executable, DuckDB path, log, refresh-window, write-window, or alert/log
retention fields.

Run after the first timer fire:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable
```

For the post-enable evidence checklist after the first timer fire:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable --format markdown
```

For the remaining post-enable operations gaps after the first timer fire:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable --format ops-gap
```

Before the `post-enable` preflight can pass, update the go-live evidence bundle:

- External timer enablement: enabled
- Timer evidence in go-live bundle: `<scheduler screenshot/log/config link>`

Acceptance:

- `current_backup_state.status` is `available`.
- `tushare.news.sina` and/or `tushare.major_news` has a recent
  `latest_received_at`.
- `error_rows` is `0` for homepage backup topics.
- `blank_payload_rows` is `0` for homepage backup topics.
- Homepage evidence still shows landed-data read behavior.
- Reserved ingest routes remain reserved.

## Evidence To Attach

- Completed go-live checklist:
  `docs/templates/tushare_news_backup_refresh_go_live_checklist.md`
- Go-live evidence:
  `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md`
- Scheduler/job screenshot or config excerpt without secrets.
- First scheduled-run log excerpt.
- Post-run dry-run JSON.
- Page evidence screenshot and browser/network evidence JSON.

## Rollback

- Rollback owner: `<team/person>`
- Disable the external timer.
- Leave landed rows in DuckDB unless a separate data-quality decision requires
  cleanup.
- Re-run dry-run.
- Confirm `/ui/news/choice-events/latest` still serves the homepage read path.
- Confirm `POST /ui/news/tushare-npr/ingest` remains reserved.
- Confirm `POST /api/news/tushare-npr/ingest` remains reserved.
- Attach rollback evidence to the same operations ticket or log bundle.
