# Macro Toolkit Freshness Timer Preflight Status (2026-07-20)

Owner: local-dev (arvin)
Rollback: Disable Windows task `MOSS-MacroToolkitFreshness` and stop enqueue; retain DuckDB rows.
Timer host: local Windows host (F:\MOSS-V3)
Write window: daily 06:30 host-local (UTC-4) ≈ 18:30 Asia/Shanghai
Log path: F:\MOSS-V3\data\logs\macro_toolkit_freshness_refresh.log
Receipt path: F:\MOSS-V3\data\logs\macro_toolkit_freshness_refresh_receipt.json
Current pre-enable gate: `ready` (verified 2026-07-20).
Current post-enable gate: `blocked` (scheduled receipt missing; scheduler probe did not find a runnable task).


First scheduled run evidence: <required after first timer fire; must cite scheduled receipt run_id / status / latest_observation_dates — shadow or enqueue acknowledgements are not valid>
