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

- Credential owner: LocalOps candidate owner; token value must remain secret and out of this checklist.
- Schedule owner: LocalOps candidate owner for the external timer on `DTCSMX`.
- Page acceptance owner: Codex local verifier for attached page evidence; LocalOps candidate owner for timer enablement acceptance.
- Rollback owner: LocalOps candidate owner for disabling the external timer.
- Evidence location: `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md`

Do not enable the timer until all owner fields are filled.

## Boundary Confirmation

Record `yes/no` and evidence:

| Check | Status | Evidence |
| --- | --- | --- |
| `MOSS_TUSHARE_TOKEN` is configured in the scheduled job environment. | yes | Current shell env check returned `MOSS_TUSHARE_TOKEN_MISSING`; app settings check returned `SETTINGS_TUSHARE_TOKEN_PRESENT`; the scheduled command starts in `F:\MOSS-V3`, and the refresh service resolves the token through the settings fallback without exposing it. |
| Job runs from repo root or explicitly sets repo root. | yes | Candidate local run starts in `F:\MOSS-V3`; timer packet Start in uses `F:\MOSS-V3`. |
| DuckDB path points to intended target. | yes | `F:\MOSS-V3\data\moss.duckdb` exists; command uses `--duckdb-path data/moss.duckdb` from repo root. |
| Refresh window avoids other DuckDB write/materialization jobs. | yes | Candidate window `08:15 Asia/Shanghai on trading weekdays`; `docs/MAINTENANCE.md` says DuckDB writes stay serial or explicitly locked, and `docs/templates/tushare_news_backup_refresh_scheduler_handoff.md` gives a weekday 08:15 cron shape. |
| `/ui/news/tushare-npr/ingest` remains reserved. | yes | Route boundary tests: `tests/test_write_route_auth_contract.py`, `tests/test_boundary_surface_inventory.py`; browser evidence captured no reserved write request. |
| `/api/news/tushare-npr/ingest` remains reserved. | yes | Route boundary tests: `tests/test_write_route_auth_contract.py`, `tests/test_boundary_surface_inventory.py`; browser evidence captured no reserved write request. |
| Homepage still reads via `/ui/news/choice-events/latest`. | yes | Browser evidence JSON: `frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.json`. |

Do not enable the timer if any boundary check is `no`.

## Dry-Run Evidence

Run before first refresh:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

Record:

- Dry-run timestamp: 2026-06-03 controlled local pre-run; see evidence bundle.
- `current_backup_state.status`: `available`
- `tushare.news.sina.latest_received_at`: `2026-06-01T08:19:56+00:00`
- `tushare.major_news.latest_received_at`: `2026-06-01T06:44:00+00:00`
- `tushare.npr.latest_received_at`: `2026-05-19T08:50:00+00:00`
- `error_rows`: all inspected backup topics `0`
- `blank_payload_rows`: all inspected backup topics `0`
- Dry-run evidence link: `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md`

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

- First-run timestamp: 2026-06-03 controlled local first run; see evidence bundle.
- Command form: sync
- Exit status or queue `status`: completed
- Actor: local script `scripts/refresh_tushare_news_backup.py`
- Message id if queued: not queued
- Worker completion evidence if queued: not applicable
- First-run evidence link: `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md`

Do not enable the recurring timer if the first run fails or if queued work cannot
be matched to a completed worker log.

## Post-Run Dry-Run Evidence

Run after the first refresh finishes:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

Record:

- Post-run dry-run timestamp: 2026-06-03 controlled local post-run; see evidence bundle.
- `tushare.news.sina.latest_received_at`: `2026-06-03T20:19:24+00:00`
- `tushare.major_news.latest_received_at`: `2026-06-03T19:43:00+00:00`
- `tushare.npr.latest_received_at`: `2026-05-19T08:50:00+00:00`
- `error_rows`: all inspected backup topics `0`
- `blank_payload_rows`: all inspected backup topics `0`
- Post-run dry-run evidence link: `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md`

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

- Page timestamp: `2026-06-03T12:45:10.381Z`
- Visible source/status label: Tushare fallback, from landed-data read path.
- Visible headline source: Tushare
- Screenshot or browser evidence: `frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.png`; `frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.json`
- Page evidence owner sign-off: Codex local verifier, 2026-06-04; LocalOps candidate owner accepts this evidence for the `DTCSMX` timer packet pending token proof.

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
- `python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable --format markdown`
  shows `Ready to create timer: true`.
- `python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable --format ops-gap`
  shows no remaining pre-enable operations gaps.

For a combined read-only review of pre-enable and post-enable gates, run:

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

After the first scheduled run, inspect remaining post-enable operations gaps:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable --format markdown
```

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable --format ops-gap
```

Decision:

- Enable timer: yes
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

Rollback owner: LocalOps candidate owner for disabling the external timer.

Rollback steps:

1. Disable the external timer.
2. Leave landed rows in DuckDB unless data-quality review requires cleanup.
3. Confirm `/ui/news/tushare-npr/ingest` and `/api/news/tushare-npr/ingest`
   remain reserved.
4. Rerun dry-run and homepage verification.
5. Attach rollback evidence to the same ticket/log bundle.
