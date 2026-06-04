# Tushare News Backup Timer Preflight Status

Status timestamp: 2026-06-03

External timer is not enabled. Do not enable the timer until the `pre-enable`
preflight returns `pass`.

This status is a handoff summary of the read-only preflight output. It does not
call Tushare, write DuckDB, enqueue the actor, create a scheduler job, or open
reserved ingest routes.

External operations gap packet:
`docs/handoff/2026-06-03-tushare-news-backup-timer-ops-gap-packet.md`.

## Combined Status

Command:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all
```

This prints both the `pre-enable` and `post-enable` reports in one read-only
bundle. It is for review only and does not enable the timer.

Machine-readable JSON `ops_gap`:

- `ops_gap.ready_to_create_timer` is true only after `pre-enable` passes.
- `ops_gap.immediate_next_actions` contains the current `pre-enable` items.
- `ops_gap.deferred_post_enable_next_actions` contains only first-scheduled-run
  evidence items.
- `ops_gap.deferred_until` records when deferred items become actionable.
- `ops_gap.required_pre_enable_inputs` lists the owner, evidence location,
  host, DuckDB path, Python path, log path, window, alert/log owner, sign-off,
  and enable-decision inputs to collect before creating the timer.
- `ops_gap.required_post_enable_inputs` lists the first scheduled-run evidence
  inputs to collect after the timer fires.
- `ops_gap.required_boundary_confirmations` lists the checklist boundary rows
  that must be marked `yes` with evidence before timer creation.

Ready to create timer: `false`

Markdown handoff command:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all --format markdown
```

Operator go/no-go command:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable --format markdown
```

Current pre-enable operations gap command:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable --format ops-gap
```

Operations gap packet command:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage all --format ops-gap
```

Post-enable evidence checklist command:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable --format markdown
```

Post-enable operations gap command:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable --format ops-gap
```

Combined verdict: `blocked`

Blocking stages: `pre-enable`, `post-enable`

Pre-enable summary: `6 pass / 5 blocked`

Post-enable summary: `6 pass / 7 blocked`

## Operator Fill Order

1. Fill owner fields first in
   `docs/templates/tushare_news_backup_refresh_go_live_checklist.md`.
2. Confirm boundary rows with evidence, without exposing secrets.
3. Complete the timer enablement packet in
   `docs/templates/tushare_news_backup_timer_enablement_packet.md`.
4. Record page acceptance sign-off for the attached homepage evidence.
5. Set Enable timer to yes after pre-enable evidence is accepted, then rerun `--stage pre-enable` before creating the external timer.
6. After the first scheduled run, attach timer evidence and rerun
   `--stage post-enable`.

## Activation Sequence

Immediate stage: `pre-enable`

Post-enable inputs remain deferred until `pre-enable` returns `pass` and the
first scheduled run finishes.

Do not create the external timer while `pre-enable` is blocked.
After `pre-enable` passes, create the external timer outside this packet and
collect first-run evidence.

## Required Boundary Confirmations

Mark these checklist boundary rows `yes` with evidence before rerunning `pre-enable`:

| Confirmation | Target document | Evidence to attach |
| --- | --- | --- |
| `MOSS_TUSHARE_TOKEN` is configured in the scheduled job environment. | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Environment proof without exposing token. |
| Job runs from repo root or explicitly sets repo root. | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Scheduler command, working directory, or job log evidence. |
| DuckDB path points to intended target. | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | DuckDB path used by the scheduled job. |
| Refresh window avoids other DuckDB write/materialization jobs. | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Calendar, runbook, or operations note proving no writer overlap. |
| `/ui/news/tushare-npr/ingest` remains reserved. | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Route test or output showing the UI ingest route remains reserved. |
| `/api/news/tushare-npr/ingest` remains reserved. | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Route test or output showing the API ingest route remains reserved. |
| Homepage still reads via `/ui/news/choice-events/latest`. | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Page/API evidence that the homepage uses the read-only landed-data path. |

## Required External Inputs

Fill these before rerunning `pre-enable`:

| Input | Target document | Evidence to attach |
| --- | --- | --- |
| Credential owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person responsible for `MOSS_TUSHARE_TOKEN`; no token value. |
| Schedule owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person responsible for the external timer. |
| Page acceptance owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person accepting homepage fallback evidence. |
| Rollback owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person who can disable the timer. |
| Evidence location | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Ticket, path, or log bundle that holds the go-live evidence. |
| Timer host | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Hostname or scheduler host identifier. |
| Repository root | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Absolute repo path used as job working directory. |
| Python executable | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Absolute Python path on the timer host. |
| DuckDB path | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | DuckDB file path used by the scheduled job. |
| Log path | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Absolute scheduler log path. |
| Refresh window | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Local time and timezone. |
| Write-window exclusion note | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Evidence that the job avoids other DuckDB writers. |
| Alert/log retention owner | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Team/person responsible for refresh alerts and log retention. |
| Page evidence owner sign-off | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Sign-off for the attached homepage screenshot and browser JSON. |
| Enable timer decision | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Set to yes after pre-enable evidence is accepted, then rerun pre-enable before creating the external timer. |

## Post-Enable Inputs

Fill these only after the first scheduled run:

| Input | Target document | Evidence to attach |
| --- | --- | --- |
| Enabled by | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person who enabled the external timer. |
| Enabled at | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Timestamp with timezone. |
| Timer evidence | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Scheduler screenshot, job config excerpt, or first scheduled-run log without secrets. |
| Timer evidence in go-live bundle | `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md` | Same timer evidence linked from the go-live bundle. |

## Pre-Enable Status

Command:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable
```

Current verdict: `blocked`

Current blocking items:

- `owners_filled`
- `boundary_confirmation_filled`
- `timer_enablement_packet_filled`
- `page_acceptance_signoff_filled`
- `enable_timer_decision_yes`

Current `next_actions`:

| Gate | Path | Action |
| --- | --- | --- |
| `owners_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Fill Credential owner, Schedule owner, Page acceptance owner, Rollback owner, and Evidence location. |
| `boundary_confirmation_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Mark each boundary row yes and attach evidence without secrets. |
| `timer_enablement_packet_filled` | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Fill timer host, repository root, Python executable, DuckDB path, log path, refresh window, write-window note, alert/log retention owner, and packet owners. |
| `page_acceptance_signoff_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Fill Page evidence owner sign-off. |
| `enable_timer_decision_yes` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Set Enable timer to yes after pre-enable evidence is accepted, then rerun pre-enable before creating the external timer. |

## Post-Enable Status

Command:

```powershell
python scripts/tushare_news_backup_timer_preflight.py --stage post-enable
```

Current verdict: `blocked`

Current blocking items:

- `owners_filled`
- `boundary_confirmation_filled`
- `timer_enablement_packet_filled`
- `page_acceptance_signoff_filled`
- `enable_timer_decision_yes`
- `timer_evidence_filled`
- `post_enable_evidence_confirms_timer_enabled`

Additional post-enable `next_actions`:

| Gate | Path | Action |
| --- | --- | --- |
| `timer_evidence_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Fill Enabled by, Enabled at, and Timer evidence after the first scheduled run. |
| `post_enable_evidence_confirms_timer_enabled` | `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md` | Update External timer enablement to enabled and fill Timer evidence in go-live bundle. |

## Already Verified Evidence Gates

These gates currently pass in both stages:

- `checklist_exists`
- `timer_enablement_packet_exists`
- `evidence_exists`
- `refresh_and_page_evidence_attached`
- `page_artifacts_exist`
- `page_evidence_json_confirms_read_only_fallback`

Reserved routes remain reserved:

- `POST /ui/news/tushare-npr/ingest`
- `POST /api/news/tushare-npr/ingest`

Homepage read path remains `/ui/news/choice-events/latest`.
