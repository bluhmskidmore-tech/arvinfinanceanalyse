# Tushare News Backup Refresh Go-Live Checklist

Use this checklist before enabling a recurring Tushare news backup refresh. It
records evidence for the first production-like run. It does not execute refresh,
open reserved routes, or approve scheduler platform changes by itself.

## Scope

- Page/workflow: homepage `政策与资金面` card.
- Read API: `/ui/news/choice-events/latest`.
- Refresh entry point: `scripts/refresh_tushare_news_backup.py`.
- Scheduler handoff:
  `docs/templates/tushare_news_backup_refresh_scheduler_handoff.md`.
- Timer enablement packet:
  `docs/templates/tushare_news_backup_timer_enablement_packet.md`.

## Owners

Fill these before enablement:

- Credential owner: `<team/person>`
- Schedule owner: `<team/person>`
- Page acceptance owner: `<team/person>`
- Rollback owner: `<team/person>`
- Evidence location: `<ticket/path/log bundle>`

Do not enable the timer until all owner fields are filled.

## Boundary Confirmation

Record `yes/no` and evidence:

| Check | Status | Evidence |
| --- | --- | --- |
| `MOSS_TUSHARE_TOKEN` is configured in the scheduled job environment. | `<yes/no>` | `<env proof without exposing token>` |
| Job runs from repo root or explicitly sets repo root. | `<yes/no>` | `<scheduler command/log>` |
| DuckDB path points to intended target. | `<yes/no>` | `<duckdb path>` |
| Refresh window avoids other DuckDB write/materialization jobs. | `<yes/no>` | `<calendar/ops note>` |
| `/ui/news/tushare-npr/ingest` remains reserved. | `<yes/no>` | `<test/output>` |
| `/api/news/tushare-npr/ingest` remains reserved. | `<yes/no>` | `<test/output>` |
| Homepage still reads via `/ui/news/choice-events/latest`. | `<yes/no>` | `<page/API evidence>` |

Do not enable the timer if any boundary check is `no`.

## Dry-Run Evidence

Run before first refresh:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

Record:

- Dry-run timestamp: `<timestamp>`
- `current_backup_state.status`: `<value>`
- `tushare.news.sina.latest_received_at`: `<value>`
- `tushare.major_news.latest_received_at`: `<value>`
- `tushare.npr.latest_received_at`: `<value>`
- `error_rows`: `<per-topic values>`
- `blank_payload_rows`: `<per-topic values>`
- Dry-run evidence link: `<ticket/path/log bundle>`

Acceptance:

- `current_backup_state.status` is `available`.
- Existing `error_rows` and `blank_payload_rows` are understood and accepted
  before refresh.

## First-Run Evidence

Run exactly one scheduled-equivalent command from the intended host:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina
```

Or, when the worker queue is the approved path:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --enqueue
```

Record:

- First-run timestamp: `<timestamp>`
- Command form: `<sync/enqueue>`
- Exit status or queue `status`: `<value>`
- Actor: `<value>`
- Message id if queued: `<value>`
- Worker completion evidence if queued: `<log link>`
- First-run evidence link: `<ticket/path/log bundle>`

Do not enable the recurring timer if the first run fails or if queued work cannot
be matched to a completed worker log.

## Post-Run Dry-Run Evidence

Run after the first refresh finishes:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

Record:

- Post-run dry-run timestamp: `<timestamp>`
- `tushare.news.sina.latest_received_at`: `<value>`
- `tushare.major_news.latest_received_at`: `<value>`
- `tushare.npr.latest_received_at`: `<value>`
- `error_rows`: `<per-topic values>`
- `blank_payload_rows`: `<per-topic values>`
- Post-run dry-run evidence link: `<ticket/path/log bundle>`

Acceptance:

- `tushare.news.sina` and/or `tushare.major_news` has a recent
  `latest_received_at`.
- `error_rows` is `0` for topics the homepage should use.
- `blank_payload_rows` is `0` for topics the homepage should use.
- Row counts did not unexpectedly drop to zero.

## Page Evidence

After landed rows are verified, open the homepage and record:

Current controlled local page evidence for the first refresh is recorded in
`docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md`.

- Page timestamp: `<timestamp>`
- Visible source/status label: `<value>`
- Visible headline source: `<Choice/Tushare>`
- Screenshot or browser evidence: `<path/link>`
- Page evidence owner sign-off: `<team/person>`

Acceptance:

- The page reads already landed data, not automatic ingest.
- Choice permission state is shown only when no usable Tushare fallback is
  available.
- Usable Tushare policy/funding headlines appear as fallback when present.

## Enablement Decision

Do not enable the timer unless all of these are true:

- Owner fields are filled.
- Boundary confirmation checks are `yes`.
- Dry-run evidence is attached.
- First-run evidence is attached.
- Post-run dry-run evidence is attached.
- Page evidence is attached.
- Rollback owner is assigned.
- `python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable`
  returns `pass`.

For a combined read-only review of pre-enable and post-enable gates, run:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all
```

Decision:

- Enable timer: `<yes/no>`
- Enabled by: `<team/person>`
- Enabled at: `<timestamp>`
- Timer evidence: `<scheduler screenshot/log/config link>`
- Timer enablement packet: `<filled packet path/link>`

After the first scheduled run, record the timer evidence above and rerun:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable
```

Update the go-live evidence bundle so it no longer says `not enabled`:

- External timer enablement: enabled
- Timer evidence in go-live bundle: `<scheduler screenshot/log/config link>`

## Rollback

Rollback owner: `<team/person>`

Rollback steps:

1. Disable the external timer.
2. Leave landed rows in DuckDB unless data-quality review requires cleanup.
3. Confirm `/ui/news/tushare-npr/ingest` and `/api/news/tushare-npr/ingest`
   remain reserved.
4. Rerun dry-run and homepage verification.
5. Attach rollback evidence to the same ticket/log bundle.
