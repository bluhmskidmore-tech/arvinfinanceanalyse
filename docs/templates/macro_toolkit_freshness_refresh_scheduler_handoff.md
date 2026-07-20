# Macro Toolkit Freshness Refresh Scheduler Handoff

The repository supplies the freshness actor, CLI, tests, and fail-closed
preflight. Operations owns the external timer and its runtime credentials.

- Actor: `refresh_macro_toolkit_freshness`
- Safe review: `python scripts/macro_toolkit_freshness_refresh.py --dry-run`
- Timer invocation: `python scripts/macro_toolkit_freshness_refresh.py --enqueue`
- Synchronous first-run validation: `python scripts/macro_toolkit_freshness_refresh.py --run-once`

Pipeline (single-writer, sequential):

1. `run_commodity_daily_ingest` (default core products, 14-day lookback)
2. `refresh_public_cross_asset_headlines` (CSI300/500, copper CA.*, DR007, …)
3. Choice `EMM00088132` 7-day reverse-repo policy rate (45-day rolling window; no carry-forward)
4. `refresh_tushare_ncd_shibor_proxy` (five SHIBOR tenors; preserves backfilled history)
5. `materialize_cffex_member_rank` for the latest weekday via `tushare` (soft-fail)

Do not overlap this job with another DuckDB writer. Recommended schedule:
daily at `18:30` in `Asia/Shanghai` (after A-share / commodity settlement).
Treat the first enablement as a shadow run. After enablement, retain the
scheduler configuration, durable log location, first successful `run_id`, and
max(`trade_date`) for `fact_commodity_futures_daily`, `CA.CSI300`, `CA.CSI500`,
`CA.COPPER` / `NHCI.NH`, `EMM00088132`, all five `NCD.SHIBOR.*` tenors, and
`fact_cffex_member_rank_daily`.

Optional local Windows installer
(`scripts/install_macro_toolkit_freshness_timer.ps1`) registers a daily
`18:30` task that runs `--run-once` (synchronous, no Dramatiq worker required).
Production hosts with a live worker should prefer the approved `--enqueue`
command from the enablement packet.
