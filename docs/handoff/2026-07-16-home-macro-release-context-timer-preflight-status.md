# Homepage Macro Release Context Timer Preflight Status

- Repository status: repo-complete
- Operations status: blocked pending named owner, host, write window, log path, rollback, approved run-once, and first scheduled evidence
- First scheduled run evidence: <required after timer enablement>
- Scheduler configuration evidence: <required after timer enablement>
- Durable log evidence: <required after timer enablement>
- First successful scheduled run ID: <required after timer enablement>
- NBS GDP shadow receipt: <required `run_id`, `release_url`, `content_sha256`, `report_period`, `value`, selected series, and `selected_vendor`>
- NBS GDP archive receipt: <required ingest batch ID plus immutable raw and normalized archive paths>
- Write safety: <required single-writer window evidence>
- Rollback: <required procedure to disable NBS selection without deleting governed history>
- Current gate remains `repo-complete`; `ops_status=blocked` until all placeholders are completed and approved.

## Manual run-once evidence

- `home-macro-release-20260717T071136Z-95534f7e`: partial. CPI advanced;
  PPI/GDP were blocked by vendor `NaN` rows and PMI had no new observation.
- Adapter boundary fixed to discard non-finite vendor rows while preserving
  legitimate zero values; strict ingest validation remains enabled.
- `home-macro-release-20260717T071832Z-9ea45c9b`: partial. PPI advanced to
  `2026-06-01`, GDP advanced to `2026-03-31`, CPI remained at `2026-06-01`,
  and PMI remained at `2026-06-01`.
- Canonical service tie-out: CPI `1.0` versus `1.2`; PPI `4.1` versus `3.9`;
  GDP `5.0` versus `5.0`; PMI `50.3` versus `50.0`. Units and vendor evidence
  matched the configured contracts. After the confirmed period-end freshness
  correction, CPI/PPI/PMI are ready while GDP remains stale at `2026-03-31`;
  formal cutover remains blocked until GDP advances.

Run `python scripts/home_macro_release_refresh_timer_preflight.py` after filling the checklist, enablement packet, and this evidence record. A nonzero exit is an intentional stop signal.
