# Homepage Macro Release Refresh Scheduler Handoff

The repository supplies the refresh actor, CLI, tests, and fail-closed preflight. Operations owns the external timer and its runtime credentials.

- Actor: `refresh_home_macro_release_sources`
- Safe review: `python scripts/home_macro_release_refresh.py --dry-run`
- Timer invocation: `python scripts/home_macro_release_refresh.py --enqueue`
- Synchronous first-run validation: `python scripts/home_macro_release_refresh.py --run-once`

Do not overlap this job with another DuckDB writer; preserve a single-writer
window. CPI and PPI use the governed Tushare macro ingest. GDP selects the
freshest governed observation, preferring `nbs.macro.cn_gdp.quarterly` over
Tushare for the same report period; Tushare remains the deterministic fallback.
PMI is limited to `tushare_macro`.
Recommended schedule: daily at `10:30` and `18:30` in `Asia/Shanghai`. Treat
the first enablement as a shadow run. After enablement, retain the scheduler
configuration, durable log location, first successful `run_id`, and the four
series' latest observation dates as post-enable evidence. For GDP also retain
`release_url`, `content_sha256`, `report_period`, `value`, selected series,
`selected_vendor`, ingest batch ID, and immutable raw/normalized archive paths.
Discovery follows the official NBS listing; operators do not maintain a
per-release URL.


The timer is not enabled by this repository change. Complete the go-live checklist and preflight first.
