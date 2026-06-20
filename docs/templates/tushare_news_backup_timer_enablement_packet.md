# Tushare News Backup Timer Enablement Packet

This packet does not enable the timer. It is an operations fill-in packet for
the recurring Tushare news backup refresh after the go-live checklist and
preflight are complete.

Use `docs/handoff/2026-06-03-tushare-news-backup-timer-ops-gap-packet.md` to
track the external owner, host, runtime, sign-off, and evidence inputs that must
be filled before this packet can pass preflight.

## Ownership And Runtime

- Credential owner: LocalOps candidate owner; token value must remain secret and out of this packet.
- Schedule owner: LocalOps candidate owner for the external timer on `DTCSMX`.
- Page acceptance owner: Codex local verifier for attached page evidence; LocalOps candidate owner for timer enablement acceptance.
- Rollback owner: LocalOps candidate owner for disabling the external timer.
- Timer host: `DTCSMX` candidate local Windows host; timer not enabled.
- Repository root: `F:\MOSS-V3`
- Python executable: `C:\Users\arvin\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- DuckDB path: `F:\MOSS-V3\data\moss.duckdb`
- Log path: `F:\MOSS-V3\logs\tushare-news-backup-refresh.log`
- Refresh window: 08:15 Asia/Shanghai on trading weekdays.
- Write-window exclusion note: Candidate weekday 08:15 window follows scheduler handoff shape and keeps this refresh as a single DuckDB writer job; `docs/MAINTENANCE.md` requires DuckDB writes to stay serial or explicitly locked.
- Alert/log retention owner: LocalOps candidate owner; retain `F:\MOSS-V3\logs\tushare-news-backup-refresh.log` and first scheduled-run evidence for 30 days.

Template placeholders for a different timer host remain:

- Credential owner: `<team/person>`
- Schedule owner: `<team/person>`
- Rollback owner: `<team/person>`
- Timer host: `<hostname>`
- Python executable: `<absolute python path>`
- DuckDB path: `data/moss.duckdb`
- Log path: `<absolute log path>`
- Refresh window: `<local time and timezone>`

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
C:\Users\arvin\AppData\Local\Python\pythoncore-3.14-64\python.exe

Arguments:
scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina

Start in:
F:\MOSS-V3
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

- Rollback owner: LocalOps candidate owner for disabling the external timer.
- Disable the external timer.
- Leave landed rows in DuckDB unless a separate data-quality decision requires
  cleanup.
- Re-run dry-run.
- Confirm `/ui/news/choice-events/latest` still serves the homepage read path.
- Confirm `POST /ui/news/tushare-npr/ingest` remains reserved.
- Confirm `POST /api/news/tushare-npr/ingest` remains reserved.
- Attach rollback evidence to the same operations ticket or log bundle.
