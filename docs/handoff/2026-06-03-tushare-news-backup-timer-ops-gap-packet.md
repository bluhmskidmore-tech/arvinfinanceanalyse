# Tushare News Backup Timer Ops Gap Packet

Status timestamp: 2026-06-03

This packet does not enable the timer. It converts the current blocked
preflight gates into external operations inputs to collect before enablement.

Do not run a real Tushare refresh from this packet.
Do not open reserved ingest routes.
External timer remains disabled.

Render this packet from the read-only preflight script with:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all --format ops-gap
```

Current verdict: `blocked`

Blocking stages: `pre-enable`, `post-enable`

Pre-enable summary: `6 pass / 5 blocked`

Post-enable summary: `6 pass / 7 blocked`

Ready to create timer: `false`

## Activation Sequence

Immediate stage: `pre-enable`

Post-enable inputs remain deferred until `pre-enable` returns `pass` and the
first scheduled run finishes.

Do not create the external timer while `pre-enable` is blocked.
After `pre-enable` passes, create the external timer outside this packet and
collect first-run evidence.

## Current Blocking Items

### Pre-Enable

- `owners_filled`
- `boundary_confirmation_filled`
- `timer_enablement_packet_filled`
- `page_acceptance_signoff_filled`
- `enable_timer_decision_yes`

### Post-Enable

- `owners_filled`
- `boundary_confirmation_filled`
- `timer_enablement_packet_filled`
- `page_acceptance_signoff_filled`
- `enable_timer_decision_yes`
- `timer_evidence_filled`
- `post_enable_evidence_confirms_timer_enabled`

## Immediate `next_actions`

| Gate | Path | Action |
| --- | --- | --- |
| `owners_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Fill Credential owner, Schedule owner, Page acceptance owner, Rollback owner, and Evidence location. |
| `boundary_confirmation_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Mark each boundary row yes and attach evidence without secrets. |
| `timer_enablement_packet_filled` | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Fill timer host, repository root, Python executable, log path, refresh window, write-window note, and packet owners. |
| `page_acceptance_signoff_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Fill Page evidence owner sign-off. |
| `enable_timer_decision_yes` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Set Enable timer to yes after pre-enable evidence is accepted, then rerun pre-enable before creating the external timer. |

## Deferred Post-Enable `next_actions`

| Gate | Path | Action |
| --- | --- | --- |
| `timer_evidence_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Fill Enabled by, Enabled at, and Timer evidence after the first scheduled run. |
| `post_enable_evidence_confirms_timer_enabled` | `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md` | Update External timer enablement to enabled and fill Timer evidence in go-live bundle. |

## Required External Inputs

Fill these before rerunning `pre-enable`:

| Input | Target document | Evidence to attach |
| --- | --- | --- |
| Credential owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person responsible for `MOSS_TUSHARE_TOKEN`; no token value. |
| Schedule owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person responsible for the external timer. |
| Page acceptance owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person accepting homepage fallback evidence. |
| Rollback owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person who can disable the timer. |
| Timer host | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Hostname or scheduler host identifier. |
| Repository root | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Absolute repo path used as job working directory. |
| Python executable | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Absolute Python path on the timer host. |
| Log path | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Absolute scheduler log path. |
| Refresh window | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Local time and timezone. |
| Write-window exclusion note | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Evidence that the job avoids other DuckDB writers. |
| Page evidence owner sign-off | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Sign-off for the attached homepage screenshot and browser JSON. |
| Enable timer decision | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Set to yes after pre-enable evidence is accepted, then rerun pre-enable before creating the external timer. |

Run `python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable` after filling pre-enable inputs.

## Post-Enable Inputs

Fill these only after the first scheduled run:

| Input | Target document | Evidence to attach |
| --- | --- | --- |
| Enabled by | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person who enabled the external timer. |
| Enabled at | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Timestamp with timezone. |
| Timer evidence | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Scheduler screenshot, job config excerpt, or first scheduled-run log without secrets. |
| Timer evidence in go-live bundle | `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md` | Same timer evidence linked from the go-live bundle. |

Run `python scripts/tushare_news_backup_timer_preflight.py --stage post-enable` after the first scheduled run.

## Boundaries

- Homepage read path remains `/ui/news/choice-events/latest`.
- `POST /ui/news/tushare-npr/ingest` remains reserved.
- `POST /api/news/tushare-npr/ingest` remains reserved.
- Do not add homepage auto-ingest behavior.
- Do not change database schema, auth/permission framework, scheduler base,
  cache base, or global SDK wrappers.
