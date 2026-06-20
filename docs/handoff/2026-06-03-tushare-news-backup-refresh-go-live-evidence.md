# Tushare News Backup Refresh Go-Live Evidence

## Scope

This evidence records the first controlled local operator refresh for the
homepage `政策与资金面` Tushare news backup path.

It does not enable an external timer, open reserved routes, change scheduler
configuration, or change the homepage read path.

## Commands

Pre-run dry-run:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

First-run refresh:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina
```

Post-run dry-run:

```powershell
python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
```

## Boundary Confirmation

- Homepage read API remains `/ui/news/choice-events/latest`.
- `POST /ui/news/tushare-npr/ingest` remains reserved.
- `POST /api/news/tushare-npr/ingest` remains reserved.
- External timer enablement: not enabled.
- Scheduler owner: pending.
- Rollback owner: pending.

## Pre-Run Dry-Run Evidence

`current_backup_state.status`: `available`

| Topic | Rows | Latest received at | Error rows | Blank payload rows |
| --- | ---: | --- | ---: | ---: |
| `tushare.major_news` | 800 | `2026-06-01T06:44:00+00:00` | 0 | 0 |
| `tushare.news.sina` | 100 | `2026-06-01T08:19:56+00:00` | 0 | 0 |
| `tushare.npr` | 1 | `2026-05-19T08:50:00+00:00` | 0 | 0 |

## First-Run Evidence

Result:

```text
status = completed
fetched = 1203
inserted = 1203
purged_expired = 97
```

Breakdown:

| Source | Fetched | Inserted | Notes |
| --- | ---: | ---: | --- |
| `policy` | 20 | 20 | Tushare policy leg |
| `news/sina` | 100 | 100 | `news_src=sina` |
| `cctv` | 37 | 37 | CCTV news leg |
| `major` | 800 | 800 | Major news leg |
| `research` | 246 | 246 | Research/news leg |

## Post-Run Dry-Run Evidence

`current_backup_state.status`: `available`

| Topic | Rows | Latest received at | Error rows | Blank payload rows |
| --- | ---: | --- | ---: | ---: |
| `tushare.major_news` | 1600 | `2026-06-03T19:43:00+00:00` | 0 | 0 |
| `tushare.news.sina` | 200 | `2026-06-03T20:19:24+00:00` | 0 | 0 |
| `tushare.npr` | 2 | `2026-05-19T08:50:00+00:00` | 0 | 0 |

## Acceptance

- `tushare.major_news` and `tushare.news.sina` refreshed to `2026-06-03`.
- `error_rows` is `0` for all inspected backup topics.
- `blank_payload_rows` is `0` for all inspected backup topics.
- `tushare.npr` remains stale at `2026-05-19T08:50:00+00:00`, which matches the
  documented policy-source freshness risk.
- Homepage page evidence is attached below and shows the Tushare landed-data
  fallback path.
- External timer remains disabled until owner fields and page evidence are
  completed in `docs/templates/tushare_news_backup_refresh_go_live_checklist.md`.

## Page Evidence

Browser evidence timestamp: `2026-06-03T12:45:10.381Z`
(`2026-06-03 20:45:10` Asia/Shanghai).

Artifacts:

- Screenshot:
  `frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.png`
- Browser/network evidence JSON:
  `frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.json`

Visible homepage card state:

- Page URL: `http://127.0.0.1:5888/`
- Card: homepage `政策与资金面`.
- Visible source label:
  `来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）`.
- Visible status label: `来源状态：Tushare 兜底`.
- Visible refresh label: `刷新：随页面查询读取已落库数据`.
- Visible headline source: `Tushare` fallback.
- Visible headline topic: `市场快讯`.
- Visible data timestamp: `06-03 20:17`.

Browser checks:

- `hasReadLandedCopy`: `true`.
- `hasAutoUpdateCopy`: `false`.
- `hasTushareCopy`: `true`.
- `hasChoicePermissionCopy`: `false` because usable Tushare fallback is shown
  instead.
- `hasNewsSourceFailureCopy`: `false`.
- `hasNewsItems`: `true`.
- `hasReservedIngestWriteRequest`: `false`.

Network path observed by the browser:

- All captured news requests were `GET /ui/news/choice-events/latest`.
- Captured macro page reads covered the six Choice macro topics and the three
  Tushare fallback topics: `tushare.major_news`, `tushare.news.sina`, and
  `tushare.npr`.
- Captured news responses returned HTTP `200`.
- No browser request was sent to `POST /ui/news/tushare-npr/ingest`.
- No browser request was sent to `POST /api/news/tushare-npr/ingest`.

## Remaining Before Timer Enablement

- Assign credential owner, schedule owner, page acceptance owner, and rollback
  owner.
- Add page acceptance owner sign-off for the attached homepage evidence.
- Confirm the selected timer host runs from the repository root and avoids other
  DuckDB write/materialization jobs.
- Run `python scripts/tushare_news_backup_timer_preflight.py` and require a
  `pass` verdict before enabling the timer.
- Enable the timer only after the checklist decision is explicitly set to yes.
